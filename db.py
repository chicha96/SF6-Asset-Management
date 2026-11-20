"""SQLite demonstration store for SF6 inventory and multi-vehicle custody simulation.
All scenario data and trips are synthetic. No RFID/GPS hardware is connected.
"""
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_FILE = Path(os.getenv('SF6_DB_PATH', Path(__file__).with_name('sf6_demo.db')))
BAYS = [(f'BAY-{i:03d}', typ, 145, 85.0) for i, typ in enumerate(
    ['Feeder', 'Feeder', 'Transformer', 'Bus Coupler'], 1)]
CAPACITY = 27.3  # illustrative planning gas fill only, not an actual approved rating
MAX_CYLINDERS_PER_TRUCK = 8  # demonstration capacity, NOT a weight or legal transport rating
VEHICLE_SEEDS = [
    ('VEH-001', 'SUB-001', 'Available'),
    ('VEH-002', 'SUB-001', 'Available'),
    ('VEH-003', 'DEPOT-001', 'Available'),
]
SITES = ('SUB-001', 'DEPOT-001')


def connection():
    c = sqlite3.connect(str(DB_FILE), check_same_thread=False, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    return c


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def init_db():
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    with connection() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS bays (
          id TEXT PRIMARY KEY, bay_type TEXT NOT NULL, voltage_kv INTEGER NOT NULL,
          installed_kg REAL NOT NULL, recovery_efficiency REAL NOT NULL DEFAULT 0.98);
        CREATE TABLE IF NOT EXISTS cylinders (
          id TEXT PRIMARY KEY, rfid TEXT NOT NULL UNIQUE, max_fill_kg REAL NOT NULL,
          gas_kg REAL NOT NULL CHECK(gas_kg>=0), bay_id TEXT, location TEXT NOT NULL,
          gas_condition TEXT NOT NULL, quality_approved INTEGER NOT NULL DEFAULT 0,
          FOREIGN KEY(bay_id) REFERENCES bays(id));
        CREATE TABLE IF NOT EXISTS vehicles (
          id TEXT PRIMARY KEY, location TEXT NOT NULL, status TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS movements (
          seq INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL,
          cylinder_id TEXT NOT NULL, event TEXT NOT NULL, from_location TEXT NOT NULL,
          to_location TEXT NOT NULL, vehicle_id TEXT, operator TEXT NOT NULL,
          note TEXT, FOREIGN KEY(cylinder_id) REFERENCES cylinders(id));
        CREATE TABLE IF NOT EXISTS quality_tests (
          seq INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL,
          cylinder_id TEXT NOT NULL, purity_pct REAL, moisture_ppmv REAL,
          method TEXT, result TEXT NOT NULL, note TEXT,
          FOREIGN KEY(cylinder_id) REFERENCES cylinders(id));
        CREATE TABLE IF NOT EXISTS gps_logs (
          seq INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL,
          vehicle_id TEXT NOT NULL, latitude REAL NOT NULL, longitude REAL NOT NULL,
          source TEXT NOT NULL, FOREIGN KEY(vehicle_id) REFERENCES vehicles(id));
        CREATE TABLE IF NOT EXISTS vehicle_events (
          seq INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL,
          vehicle_id TEXT NOT NULL, event TEXT NOT NULL,
          from_location TEXT NOT NULL, to_location TEXT NOT NULL,
          cylinder_count INTEGER NOT NULL, operator TEXT NOT NULL,
          note TEXT, FOREIGN KEY(vehicle_id) REFERENCES vehicles(id));
        ''')
        if c.execute('SELECT COUNT(*) FROM bays').fetchone()[0] == 0:
            c.executemany('INSERT INTO bays (id,bay_type,voltage_kv,installed_kg,recovery_efficiency) VALUES (?,?,?,?,0.98)', BAYS)
        # Adds missing vehicles to an existing V1 database without touching assets/history.
        for v in VEHICLE_SEEDS:
            c.execute('INSERT OR IGNORE INTO vehicles(id,location,status) VALUES (?,?,?)', v)
        if c.execute('SELECT COUNT(*) FROM cylinders').fetchone()[0] == 0:
            for i in range(1, 21):
                bay_id = f'BAY-{((i-1)//4)+1:03d}' if i <= 16 else None
                c.execute('''INSERT INTO cylinders
                  (id,rfid,max_fill_kg,gas_kg,bay_id,location,gas_condition,quality_approved)
                  VALUES (?,?,?,?,?,?,?,?)''', (
                  f'SF6-CYL-{i:03d}', f'RFID-{i:06d}', CAPACITY,
                  20.825 if i <= 16 else 0.0, bay_id,
                  'SUB-001' if i <= 16 else 'DEPOT-001',
                  'Used / Unverified' if i <= 16 else 'Empty', 0))
        # Legacy V1 fix: earlier versions did not have vehicle_events, and all
        # cylinder IDs now reference distinct vehicle IDs by location.
        # Never rewrite old movement records or cylinder assignments.


def get_records(table):
    allowed = {'bays', 'cylinders', 'vehicles', 'movements', 'quality_tests', 'gps_logs', 'vehicle_events'}
    if table not in allowed:
        raise ValueError('Invalid table')
    order = 'seq DESC' if table in {'movements', 'quality_tests', 'gps_logs', 'vehicle_events'} else 'id ASC'
    with connection() as c:
        return [dict(x) for x in c.execute(f'SELECT * FROM {table} ORDER BY {order}').fetchall()]


def _vehicle(c, vehicle_id):
    vehicle = c.execute('SELECT * FROM vehicles WHERE id=?', (vehicle_id,)).fetchone()
    if vehicle is None:
        raise ValueError(f'Unknown vehicle: {vehicle_id}')
    return vehicle


def move_cylinders(ids, target, operator, note='', vehicle_id='VEH-001'):
    """Atomically load/unload cylinders for *one* vehicle, with custody log."""
    ids = list(dict.fromkeys(ids))
    if not ids:
        raise ValueError('เลือกอย่างน้อยหนึ่ง Cylinder')
    if not operator.strip():
        raise ValueError('กรอกชื่อผู้ดำเนินการ')
    if target not in (*SITES, vehicle_id):
        raise ValueError('Unknown location')
    with connection() as c:
        c.execute('BEGIN IMMEDIATE')
        v = _vehicle(c, vehicle_id)
        if target == vehicle_id:
            current_count = c.execute('SELECT COUNT(*) FROM cylinders WHERE location=?', (vehicle_id,)).fetchone()[0]
            if current_count + len(ids) > MAX_CYLINDERS_PER_TRUCK:
                raise ValueError(f'{vehicle_id}: demo limit {MAX_CYLINDERS_PER_TRUCK} cylinders per vehicle')
        checked = []
        for cylinder_id in ids:
            cyl = c.execute('SELECT * FROM cylinders WHERE id=?', (cylinder_id,)).fetchone()
            if cyl is None:
                raise ValueError(f'ไม่พบ Cylinder {cylinder_id}')
            origin = cyl['location']
            if origin == target:
                raise ValueError(f'{cylinder_id} อยู่ที่ {target} อยู่แล้ว')
            if target == vehicle_id:
                if origin not in SITES:
                    raise ValueError(f'{cylinder_id}: loading requires a cylinder at a site, not another vehicle')
                if origin != v['location']:
                    raise ValueError(f'รถ {vehicle_id} อยู่ที่ {v["location"]} แต่ {cylinder_id} อยู่ที่ {origin}')
                event = 'LOADED'
            else:
                if origin != vehicle_id:
                    raise ValueError(f'{cylinder_id} ไม่ได้อยู่บนรถ {vehicle_id}')
                if target != v['location']:
                    raise ValueError(f'รถ {vehicle_id} อยู่ที่ {v["location"]} ไม่ใช่ {target}')
                event = 'UNLOADED'
            checked.append((cylinder_id, origin, event))
        for cylinder_id, origin, event in checked:
            c.execute('UPDATE cylinders SET location=? WHERE id=?', (target, cylinder_id))
            c.execute('''INSERT INTO movements(timestamp,cylinder_id,event,from_location,to_location,vehicle_id,operator,note)
                         VALUES (?,?,?,?,?,?,?,?)''',
                      (now(), cylinder_id, event, origin, target, vehicle_id, operator.strip(), note.strip()))
        count = c.execute('SELECT COUNT(*) FROM cylinders WHERE location=?', (vehicle_id,)).fetchone()[0]
        c.execute('UPDATE vehicles SET status=? WHERE id=?', ('Loaded' if count else 'Available', vehicle_id))
        c.execute('''INSERT INTO vehicle_events(timestamp,vehicle_id,event,from_location,to_location,cylinder_count,operator,note)
                     VALUES (?,?,?,?,?,?,?,?)''',
                  (now(), vehicle_id, 'LOAD' if target == vehicle_id else 'UNLOAD',
                   v['location'], v['location'], len(ids), operator.strip(), note.strip()))
    return len(checked)


def drive_vehicle(destination, operator, note='', vehicle_id='VEH-001'):
    """Simulate arrival; does not generate GPS points or real travel times."""
    if destination not in SITES:
        raise ValueError('Unknown destination')
    if not operator.strip():
        raise ValueError('กรอกชื่อผู้ดำเนินการ')
    with connection() as c:
        c.execute('BEGIN IMMEDIATE')
        v = _vehicle(c, vehicle_id)
        if v['location'] == destination:
            raise ValueError('รถอยู่ที่ปลายทางนี้แล้ว')
        onboard = [r['id'] for r in c.execute('SELECT id FROM cylinders WHERE location=? ORDER BY id', (vehicle_id,))]
        c.execute('UPDATE vehicles SET location=?, status=? WHERE id=?',
                  (destination, 'Loaded' if onboard else 'Available', vehicle_id))
        c.execute('''INSERT INTO vehicle_events(timestamp,vehicle_id,event,from_location,to_location,cylinder_count,operator,note)
                     VALUES (?,?,?,?,?,?,?,?)''',
                  (now(), vehicle_id, 'ARRIVED (SIMULATED)', v['location'], destination,
                   len(onboard), operator.strip(), note.strip()))
        for cylinder_id in onboard:
            c.execute('''INSERT INTO movements(timestamp,cylinder_id,event,from_location,to_location,vehicle_id,operator,note)
                         VALUES (?,?,?,?,?,?,?,?)''',
                      (now(), cylinder_id, 'VEHICLE_TRIP', v['location'], destination,
                       vehicle_id, operator.strip(), note.strip()))
    return len(onboard)


def record_quality(cylinder_id, purity, moisture, method, result, note=''):
    if result not in {'PASS (reviewed)', 'REVIEW', 'PENDING'}:
        raise ValueError('Invalid result')
    if not (0 <= purity <= 100) or moisture < 0:
        raise ValueError('Invalid reading')
    if not method.strip():
        raise ValueError('โปรดระบุวิธีการทดสอบ')
    with connection() as c:
        cyl = c.execute('SELECT * FROM cylinders WHERE id=?', (cylinder_id,)).fetchone()
        if not cyl:
            raise ValueError('Unknown cylinder')
        if cyl['gas_kg'] == 0:
            raise ValueError('Empty cylinder')
        c.execute('''INSERT INTO quality_tests(timestamp,cylinder_id,purity_pct,moisture_ppmv,method,result,note)
                     VALUES (?,?,?,?,?,?,?)''',
                  (now(), cylinder_id, purity, moisture, method, result, note))
        c.execute('UPDATE cylinders SET gas_condition=?,quality_approved=0 WHERE id=?',
                  ('Quality Tested / Awaiting Approval' if result == 'PASS (reviewed)' else 'Quarantined / Needs Review', cylinder_id))


def approve_quality(cylinder_id, operator, standard_reference):
    if not operator.strip() or not standard_reference.strip():
        raise ValueError('ต้องกรอกชื่อผู้อนุมัติและเอกสารเกณฑ์การอนุมัติ')
    with connection() as c:
        c.execute('BEGIN IMMEDIATE')
        cyl = c.execute('SELECT * FROM cylinders WHERE id=?', (cylinder_id,)).fetchone()
        if not cyl or cyl['gas_kg'] <= 0:
            raise ValueError('No gas to approve')
        test = c.execute('SELECT * FROM quality_tests WHERE cylinder_id=? ORDER BY seq DESC LIMIT 1', (cylinder_id,)).fetchone()
        if not test or test['result'] != 'PASS (reviewed)':
            raise ValueError('ต้องมีผลตรวจ PASS ล่าสุดก่อนอนุมัติ')
        c.execute('UPDATE cylinders SET quality_approved=1,gas_condition=? WHERE id=?',
                  ('Qualified for Reuse', cylinder_id))
        c.execute('''INSERT INTO movements(timestamp,cylinder_id,event,from_location,to_location,vehicle_id,operator,note)
                     VALUES (?,?,?,?,?,?,?,?)''',
                  (now(), cylinder_id, 'QUALITY_APPROVED', cyl['location'], cyl['location'], None,
                   operator.strip(), standard_reference.strip()))


def add_gps(lat, lon, source, vehicle_id='VEH-001'):
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError('Invalid GPS coordinates')
    if not source.strip():
        raise ValueError('Provide GPS data source')
    with connection() as c:
        _vehicle(c, vehicle_id)
        c.execute('''INSERT INTO gps_logs(timestamp,vehicle_id,latitude,longitude,source)
                     VALUES (?,?,?,?,?)''', (now(), vehicle_id, lat, lon, source.strip()))


def reset_demo():
    # Reset is intended for local demo only; no production migration semantics.
    if DB_FILE.exists():
        DB_FILE.unlink()
    init_db()
