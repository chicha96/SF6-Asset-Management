# SF₆ Asset Management — Interactive Streamlit Demo

A browser-based mini-project prototype with Dashboard, GIS Bay records, unique RFID cylinder lookup, custody-based cylinder transfer simulation, quality tests, vehicle status, optional recorded GPS observations, CSV export and an SQLite audit log.

## Scenario

| Item | Demo value | Basis |
|---|---:|---|
| GIS Bays | 4 | Synthetic reference case |
| Initial SF₆ per Bay | 85 kg | Illustrative placeholder; verify the model-specific OEM plate |
| Total installed | 340 kg | Calculated |
| Recovery efficiency | 98% | Synthetic assumption |
| Planned recovery | 333.2 kg | Calculated |
| Treatment mass yield | 99% | Planning scenario only, **not gas purity** |
| Filled cylinders | 16 × 20.825 kg | Synthetic recovery allocation |
| Empty spare cylinders | 4 | Synthetic scenario |
| Cylinder planning fill cap | 27.3 kg | Placeholder; not operational filling authorization |
| Vehicle | VEH-001 | Synthetic |
| Central depot | DEPOT-001 | Synthetic |

## Local installation

Install Python 3.10+ and run:

```bash
pip install -r requirements.txt
streamlit run app.py
```

The command prints a local URL such as `http://localhost:8501` to open in your browser. The SQLite database is created at `sf6_demo.db` on first launch.

## Publish as an actual website URL

1. Create a GitHub repository and upload `app.py`, `db.py`, and `requirements.txt` (and optionally this README). **Do not upload** `sf6_demo.db` with personal or sensitive information.
2. Sign in to [Streamlit Community Cloud](https://share.streamlit.io/) and choose **Create app**.
3. Point it to your GitHub repository, branch `main` and entrypoint `app.py`.
4. Select **Deploy**. Streamlit gives your app a public `.streamlit.app` URL.
5. Use the URL to demonstrate the software to your professor.

**Important:** This package cannot create a public hosted URL by itself. Cloud platform deployment requires your own account action. Local SQLite data on Streamlit Community Cloud can disappear on app restarts, and app visitors share the same demo state. For a reliable multiuser public application, replace SQLite with hosted Postgres/Supabase, add login, roles and server-side access controls, and connect hardware systems using vetted integrations.

## Demo: RFID + cylinder movement

- Go to **Cylinder & RFID**, search `RFID-000001`.
- Go to **Movement Simulator** and load `SF6-CYL-001` from `SUB-001` onto `VEH-001`.
- Choose **Travel to destination** to move `VEH-001` to `DEPOT-001` (a simulated event, **not a GPS report**).
- Select **Unload cylinders** and scan the ID to receive it into the depot.
- Return to the Dashboard and search page. Both reflect the new physical custody status. Event History preserves timestamps.
- You can reverse the process by loading at the depot, returning the vehicle to SUB-001, and unloading.

## Quality workflow

- Enter laboratory readings and a test method in **Quality & Treatment**.
- An operator interpretation of `PASS (reviewed)` **does not automatically release gas**.
- Quality release additionally requires a manual record of approver and documented standard/procedure. The demo cannot verify IEC compliance or replace real certification.
- No treatment or gas transfers are physically performed. The treatment output is a forecast, separate from the mass in stored cylinders.

## Files

- `app.py`: Streamlit interface and charts
- `db.py`: SQLite schema, scenario data and state transition logic
- `requirements.txt`: Python dependencies
- `README.md`: setup and deployment
- `test_db.py`: tests of movements, inventory invariants and quality authorization
- `SF6_Excel_PowerBI_DataModel.xlsx` (if included): earlier reference Excel data model; the website uses its own scenario seed and does **not** dynamically sync with Excel or Power BI.

## Security and safety

This is a **simulation**, not a certified asset management product. RFID values are simulated IDs; there is no RFID reader connection. GPS is manual-observation-only. No real personnel, confidential substation information, or live vehicle location should be entered into an unprotected public demo. SF₆ handling, contaminated gas, cylinders, and transportation require trained staff and current standards/regulations.
