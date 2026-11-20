"""Streamlit frontend: educational, simulated SF6 asset management."""
import io
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from db import (init_db,get_records,move_cylinders,drive_vehicle,record_quality,
                approve_quality,add_gps,reset_demo)

st.set_page_config(page_title='SF₆ | Asset Management',page_icon='⚡',layout='wide',initial_sidebar_state='expanded')
init_db()
st.markdown('''<style>
.stApp {background:#f6f9fc;color:#16233b}
[data-testid="stSidebar"] {background:#11233f}
[data-testid="stSidebar"] * {color:#eff5ff!important}
h1,h2,h3 {color:#17365d!important}
[data-testid="stMetric"] {background:white;padding:18px;border-radius:14px;border:1px solid #e3e9f2;box-shadow:0 2px 10px #0f244009}
[data-testid="stMetricLabel"] {color:#526479}
div.stButton>button[kind="primary"] {background:#126a7a;border:0}
.small-note {color:#607188;font-size:0.9rem}
</style>''',unsafe_allow_html=True)

st.sidebar.title('⚡ SF₆ Asset Manager')
st.sidebar.caption('VERSION 1 · INTERACTIVE DEMO')
page=st.sidebar.radio('Navigation',[
    '📊 Executive Dashboard','🏭 GIS Bays','🏷️ Cylinder & RFID','🚚 Simulation · 5 Steps',
    '🧪 Quality & Treatment','📍 Vehicle & GPS','📜 Event History','ℹ️ About & Data'
])
st.sidebar.divider()
st.sidebar.info('SIMULATION ONLY — 4 Bays, 20 Cylinders, 3 Vehicles. Not connected to real RFID/GPS or gas analyzers.')

def df(table): return pd.DataFrame(get_records(table))

def notify(action):
    try:
        result=action()
        st.success('บันทึกสำเร็จ' + (f' · {result} Cylinder(s)' if isinstance(result,int) else ''))
        st.rerun()
    except (ValueError,RuntimeError) as exc:
        st.error(str(exc))

bays=df('bays'); cyl=df('cylinders'); veh=df('vehicles'); movements=df('movements'); tests=df('quality_tests'); gps=df('gps_logs'); trips=df('vehicle_events')
installed=float(bays['installed_kg'].sum())
planned_recovered=float((bays['installed_kg']*bays['recovery_efficiency']).sum())
current_mass=float(cyl['gas_kg'].sum())
qualified=float(cyl.loc[cyl['quality_approved']==1,'gas_kg'].sum())

if page=='📊 Executive Dashboard':
    st.title('SF₆ Asset Management Dashboard')
    st.caption('GIS Substation SUB-001 · Educational scenario · Data is synthetic and editable through workflows')
    a,b,c,d=st.columns(4)
    a.metric('Installed SF₆',f'{installed:,.1f} kg')
    b.metric('Planned recovered',f'{planned_recovered:,.1f} kg')
    c.metric('Cylinder inventory',f'{len(cyl)} cylinders')
    d.metric('Approved for reuse',f'{qualified:,.2f} kg')
    if abs(current_mass-planned_recovered)>.001:
        st.warning(f'Cylinder inventory ({current_mass:.3f} kg) differs from planned recovered mass ({planned_recovered:.3f} kg). Review gas transfers / mass balance.')
    st.info('Initial state models recovery already assigned to 16 cylinders at SUB-001. 4 spare cylinders are empty at DEPOT-001. Planned treatment output is only a forecast, not approved inventory.')
    left,right=st.columns([1.3,1])
    with left:
        plot=bays[['id','installed_kg']].copy()
        plot['planned_recovery_kg']=bays['installed_kg']*bays['recovery_efficiency']
        fig=go.Figure()
        fig.add_bar(x=plot['id'],y=plot['installed_kg'],name='Installed (kg)',marker_color='#236d99')
        fig.add_bar(x=plot['id'],y=plot['planned_recovery_kg'],name='Planned Recovery (kg)',marker_color='#45b69c')
        fig.update_layout(title='SF₆ by GIS Bay',barmode='group',height=360,margin=dict(l=10,r=10,t=55,b=10),paper_bgcolor='white',plot_bgcolor='white',legend_orientation='h')
        st.plotly_chart(fig,use_container_width=True)
    with right:
        counts=cyl['gas_condition'].value_counts().reset_index()
        counts.columns=['Condition','Cylinders']
        fig=px.pie(counts,values='Cylinders',names='Condition',hole=.62,title='Cylinder Gas Condition',color_discrete_sequence=['#1c739b','#50bcb0','#f6bd60','#a8b7c9'])
        fig.update_layout(height=360,margin=dict(l=10,r=10,t=55,b=10),paper_bgcolor='white')
        st.plotly_chart(fig,use_container_width=True)
    a,b,c=st.columns(3)
    a.metric('At Substation',int((cyl['location']=='SUB-001').sum()))
    b.metric('On Any Vehicle',int(cyl['location'].isin(veh['id']).sum()))
    c.metric('At Depot',int((cyl['location']=='DEPOT-001').sum()))
    st.subheader('3-vehicle fleet overview')
    fleet=veh.copy()
    fleet['Onboard Cylinders']=fleet['id'].map(cyl['location'].value_counts()).fillna(0).astype(int)
    fleet['Onboard SF₆ (kg)']=fleet['id'].map(cyl.groupby('location')['gas_kg'].sum()).fillna(0).round(3)
    st.dataframe(fleet.rename(columns={'id':'Vehicle ID','location':'Current Site','status':'Vehicle Status'}),use_container_width=True,hide_index=True)
    st.caption('Each vehicle maintains a separate manifest. Positions indicate a simulated site; not live GPS coordinates.')
    st.subheader('Asset tracking overview')
    st.dataframe(cyl[['id','rfid','bay_id','gas_kg','gas_condition','location']].rename(columns={
        'id':'Cylinder','rfid':'RFID','bay_id':'Source Bay','gas_kg':'Gas Mass (kg)','gas_condition':'Gas Condition','location':'Current Location'}),
        use_container_width=True,hide_index=True)

elif page=='🏭 GIS Bays':
    st.title('GIS Bay Register')
    st.caption('4 reference Bays · 145 kV · 85 kg/Bay (illustrative, verify with manufacturer plate)')
    view=bays.copy(); view['planned_recovered_kg']=view['installed_kg']*view['recovery_efficiency']
    view['unrecovered_difference_kg']=view['installed_kg']-view['planned_recovered_kg']
    st.dataframe(view,use_container_width=True,hide_index=True)
    selected=st.selectbox('Select Bay',bays['id'])
    members=cyl[cyl['bay_id']==selected]
    st.metric('Cylinders originally allocated to '+selected,len(members))
    st.dataframe(members[['id','rfid','gas_kg','location','gas_condition']],use_container_width=True,hide_index=True)
    st.warning('Bay model and compartment gas values must be confirmed against the actual GIS manufacturer documentation before field use.')

elif page=='🏷️ Cylinder & RFID':
    st.title('Cylinder & RFID Lookup')
    q=st.text_input('Search by Cylinder ID / RFID / Bay ID',placeholder='e.g. RFID-000001 or SF6-CYL-007')
    loc=st.selectbox('Filter location',['All']+sorted(cyl['location'].unique().tolist()))
    result=cyl.copy()
    if q:
        search=(result['id'].astype(str)+' '+result['rfid'].astype(str)+' '+result['bay_id'].fillna('').astype(str))
        result=result[search.str.contains(q,case=False,regex=False)]
    if loc!='All': result=result[result['location']==loc]
    st.caption(f'{len(result)} cylinders match your search')
    st.dataframe(result.rename(columns={'id':'Cylinder ID','rfid':'RFID Tag','max_fill_kg':'Max Planning Fill (kg)','gas_kg':'Current Gas (kg)','bay_id':'Origin Bay','location':'Location','quality_approved':'Reuse Approved'}),use_container_width=True,hide_index=True)
    if len(result)==1:
        c=result.iloc[0]
        st.subheader(f"{c['id']} · {c['rfid']}")
        x,y,z=st.columns(3); x.metric('Gas mass',f"{c['gas_kg']:.3f} kg"); y.metric('Capacity (planning)',f"{c['max_fill_kg']:.1f} kg"); z.metric('Location',c['location'])
        st.write(f"Condition: **{c['gas_condition']}** · Reuse approved: **{'Yes' if c['quality_approved'] else 'No'}**")
        history=movements[movements['cylinder_id']==c['id']] if not movements.empty else pd.DataFrame()
        st.subheader('Custody event history')
        if history.empty: st.caption('No movement scans recorded yet')
        else: st.dataframe(history,use_container_width=True,hide_index=True)

elif page=='🚚 Simulation · 5 Steps':
    st.title('🚚 Multi-Vehicle Simulation')
    st.caption('Guided custody simulation for 3 independent vehicles. Select a truck, then work through each stage left to right.')
    st.info('Demonstration only. No physical RFID scan, live vehicle GPS, or actual transport clearance is performed.')
    all_ids=veh['id'].tolist()
    vehicle_id=st.selectbox('🚛 Select Vehicle',all_ids,key='simulation_vehicle')
    vehicle=veh.loc[veh['id']==vehicle_id].iloc[0]
    at=vehicle['location']
    onboard=cyl[cyl['location']==vehicle_id]
    available=cyl[cyl['location']==at]
    st.markdown(f'**Selected:** `{vehicle_id}` · **Current site:** `{at}` · **Onboard:** {len(onboard)} / 8 cylinders (illustrative demo limit)')
    c1,c2,c3=st.columns(3)
    c1.metric('Cylinders onboard',len(onboard))
    c2.metric('Gas mass onboard',f"{onboard['gas_kg'].sum():.3f} kg")
    c3.metric('Cylinders available at site',len(available))
    stage1,stage2,stage3,stage4,stage5=st.tabs([
        '① Overview & Plan','② RFID Load','③ Simulate Trip','④ RFID Unload','⑤ Audit & Verify'
    ])
    with stage1:
        st.subheader('Step 1 · Review vehicle assignment and capacity')
        st.write('Choose a truck above. Only cylinders physically registered at its current site can be loaded.')
        preview=veh.copy()
        preview['Cylinders onboard']=preview['id'].map(cyl['location'].value_counts()).fillna(0).astype(int)
        preview['Gas kg onboard']=preview['id'].map(cyl.groupby('location')['gas_kg'].sum()).fillna(0).round(3)
        st.dataframe(preview,use_container_width=True,hide_index=True)
        st.write('**Scenario:** `VEH-001` and `VEH-002` begin at `SUB-001`; `VEH-003` begins at `DEPOT-001`. All three operate independently.')
        st.caption('Planning limit 8 cylinders per truck is illustrative; actual cylinder mass, securing, loading capacity and transport rules have not been engineered.')
        st.markdown('**Next:** Go to **② RFID Load** to scan cylinders and assign them to the selected truck.')
    with stage2:
        st.subheader('Step 2 · Simulate RFID scanning and loading')
        st.write(f'Loading location for **{vehicle_id}**: `{at}`')
        st.dataframe(available[['id','rfid','gas_kg','gas_condition']].rename(columns={'id':'Cylinder','rfid':'RFID'}),hide_index=True,use_container_width=True)
        with st.form('load_'+vehicle_id):
            operator_load=st.text_input('Operator / scanner name',value='Demo Operator',key='loadoperator')
            selected_load=st.multiselect('Scan cylinder IDs (RFID identifiers shown above)',available['id'].tolist(),key='load_ids')
            load_note=st.text_input('Note (optional)',key='load_note')
            load_clicked=st.form_submit_button('Scan RFID → LOAD',type='primary')
        if load_clicked:
            notify(lambda:move_cylinders(selected_load,vehicle_id,operator_load,load_note,vehicle_id=vehicle_id))
        st.caption('Loading from a different location, loading onto another truck, and exceeding the demo capacity are blocked.')
    with stage3:
        st.subheader('Step 3 · Simulate travel to destination')
        other='DEPOT-001' if at=='SUB-001' else 'SUB-001'
        st.markdown(f'**Simulated route:** `{at}` → `{other}`')
        st.write(f'**Current manifest:** {len(onboard)} cylinders, {onboard["gas_kg"].sum():.3f} kg')
        if len(onboard)==0:
            st.warning('No cylinders on this truck. An empty relocation trip is possible and is logged separately.')
        else:
            st.dataframe(onboard[['id','rfid','gas_kg']],use_container_width=True,hide_index=True)
        with st.form('trip_'+vehicle_id):
            operator_drive=st.text_input('Driver / operator',value='Demo Driver',key='drive_operator')
            drive_note=st.text_input('Trip note (optional)',key='drive_note')
            drive_clicked=st.form_submit_button('Simulate ARRIVAL',type='primary')
        if drive_clicked:
            notify(lambda:drive_vehicle(other,operator_drive,drive_note,vehicle_id=vehicle_id))
        st.caption('Travel is an instantaneous status change; it generates no invented trip duration, GPS coordinates, or driving distance.')
    with stage4:
        st.subheader('Step 4 · Simulate arrival scan and unloading')
        st.write(f'**Truck location:** `{at}` · **Truck:** `{vehicle_id}`')
        if onboard.empty:
            st.info('No cylinders onboard. Load some in Step 2 or select a vehicle with cargo.')
        else:
            st.dataframe(onboard[['id','rfid','gas_kg','gas_condition']],use_container_width=True,hide_index=True)
        with st.form('unload_'+vehicle_id):
            operator_unload=st.text_input('Receiving operator / scanner name',value='Depot Operator',key='unload_operator')
            selected_unload=st.multiselect('Scan onboard cylinders to receive',onboard['id'].tolist(),key='unload_ids')
            unload_note=st.text_input('Receiving note (optional)',key='unload_note')
            unload_clicked=st.form_submit_button('Scan RFID → UNLOAD',type='primary')
        if unload_clicked:
            notify(lambda:move_cylinders(selected_unload,at,operator_unload,unload_note,vehicle_id=vehicle_id))
        st.caption('Only cylinders assigned to this truck can be unloaded; a scan event is appended for each cylinder.')
    with stage5:
        st.subheader('Step 5 · Verify inventory and audit trail')
        st.markdown('**All vehicles (independent status)**')
        summary=veh.copy()
        summary['Onboard']=summary['id'].map(cyl['location'].value_counts()).fillna(0).astype(int)
        st.dataframe(summary,use_container_width=True,hide_index=True)
        vtrips=trips[trips['vehicle_id']==vehicle_id] if not trips.empty else pd.DataFrame()
        events=movements[movements['vehicle_id']==vehicle_id] if not movements.empty else pd.DataFrame()
        st.markdown(f'**Vehicle event log · {vehicle_id}**')
        if vtrips.empty: st.caption('No load, trip or unload events recorded yet.')
        else: st.dataframe(vtrips,use_container_width=True,hide_index=True)
        st.markdown('**Cylinder custody history**')
        if events.empty: st.caption('No RFID custody events for this vehicle yet.')
        else: st.dataframe(events,use_container_width=True,hide_index=True)
        if not events.empty:
            st.download_button('Export this vehicle custody history',events.to_csv(index=False).encode('utf-8-sig'),f'{vehicle_id}_custody.csv','text/csv')
        st.success(f'Mass check · all cylinder gas: {cyl["gas_kg"].sum():.3f} kg / planning recovery: {planned_recovered:.3f} kg') if abs(cyl['gas_kg'].sum()-planned_recovered)<.001 else st.warning('Mass differs from planning baseline; investigate movements and gas transactions.')
        st.caption('The demo records vehicle travel and cylinder handovers; it does not prove the cylinder was physically scanned or the vehicle actually travelled.')

elif page=='🧪 Quality & Treatment':
    st.title('Gas Quality & Treatment')
    st.warning('Gas treatment and quality measurements are not simulated as verified results. Enter measured values only; reuse approval requires a documented acceptance review.')
    st.metric('Planning treatment output at 99% mass yield',f'{planned_recovered*.99:.3f} kg',help='Forecast only. Mass yield does not establish SF6 purity or compliance.')
    with st.form('quality_form'):
        eligible=cyl[cyl['gas_kg']>0]['id'].tolist()
        id_=st.selectbox('Cylinder',eligible)
        purity=st.number_input('Measured SF₆ purity (%)',0.0,100.0,99.0,step=.01)
        moisture=st.number_input('Measured moisture (ppmv)',0.0,1_000_000.0,50.0,step=1.0)
        method=st.text_input('Instrument / test method')
        result=st.selectbox('Technician interpretation',['PENDING','REVIEW','PASS (reviewed)'])
        note=st.text_input('Test certificate / note')
        submitted=st.form_submit_button('Save Test Reading')
    if submitted: notify(lambda:record_quality(id_,purity,moisture,method,result,note))
    with st.expander('Manual quality release (for controlled demonstration)'):
        st.write('Requires latest test marked PASS (reviewed), a named reviewer, and documented acceptance standard. This is a demonstration record, not an IEC certification.')
        with st.form('approval_form'):
            selected=st.selectbox('Cylinder to approve',eligible,key='approve_select')
            reviewer=st.text_input('Approver')
            standard=st.text_input('Approved procedure / standard reference')
            approved=st.form_submit_button('Record Approval')
        if approved: notify(lambda:approve_quality(selected,reviewer,standard))
    st.subheader('Test history')
    if tests.empty: st.caption('No actual tests entered yet')
    else: st.dataframe(tests,use_container_width=True,hide_index=True)

elif page=='📍 Vehicle & GPS':
    st.title('Vehicle & GPS Tracking Log')
    st.caption('Vehicle position is recorded only when actual coordinates are entered. Movement simulation does not claim live GPS.')
    st.dataframe(veh,use_container_width=True,hide_index=True)
    selected_vehicle=st.selectbox('Vehicle for GPS log',veh['id'].tolist(),key='gps_vehicle')
    with st.expander('Record verified GPS observation'):
        with st.form('gps_form'):
            lat=st.number_input('Latitude',value=0.0,min_value=-90.0,max_value=90.0,format='%.6f')
            lon=st.number_input('Longitude',value=0.0,min_value=-180.0,max_value=180.0,format='%.6f')
            source=st.text_input('Source (e.g. manual device record)')
            go=st.form_submit_button('Save GPS Observation')
        if go: notify(lambda:add_gps(lat,lon,source,vehicle_id=selected_vehicle))
    selected_gps=gps[gps['vehicle_id']==selected_vehicle] if not gps.empty else pd.DataFrame()
    if selected_gps.empty:
        st.info('No verified GPS observations for this vehicle. Map will appear when records are entered.')
    else:
        st.map(selected_gps[['latitude','longitude']].rename(columns={'latitude':'lat','longitude':'lon'}))
        st.dataframe(selected_gps,use_container_width=True,hide_index=True)

elif page=='📜 Event History':
    st.title('Audit / Transaction History')
    st.caption('Append-only demo history for cylinder loading, vehicle trips, unloading and quality approvals.')
    if movements.empty: st.info('No transaction events recorded. Try Simulation · 5 Steps.')
    else:
        st.dataframe(movements,use_container_width=True,hide_index=True)
        st.download_button('Export movement log CSV',movements.to_csv(index=False).encode('utf-8-sig'),'sf6_movement_log.csv','text/csv')
    if not trips.empty:
        st.subheader('Vehicle trip / load / unload events')
        st.dataframe(trips,use_container_width=True,hide_index=True)
    if not tests.empty:
        st.subheader('Quality tests')
        st.dataframe(tests,use_container_width=True,hide_index=True)

else:
    st.title('About the Demonstration')
    st.markdown('''### Scenario
- **1 reference substation:** `SUB-001`
- **4 GIS Bays** × **85 kg** initial installed gas = **340 kg**
- **98% planned recovery** = **333.2 kg**
- **16 filled cylinders:** 20.825 kg each; **4 empty spares**
- **3 trucks:** `VEH-001` and `VEH-002` at `SUB-001`, `VEH-003` at `DEPOT-001`; **1 central depot:** `DEPOT-001`
- **Planning capacity**: 27.3 kg/cylinder; must be checked against actual certified cylinder limits.

### How to demo for your professor
1. Open **Executive Dashboard** and review installed, planned recovered, unqualified gas.
2. Search **RFID-000001** in **Cylinder & RFID**.
3. Open **Simulation · 5 Steps** and choose `VEH-001` (or `VEH-002`).
4. Follow tabs in order: Overview → RFID Load → Simulate Trip → RFID Unload → Audit.
5. Observe updated location and scan history on the Dashboard and RFID screen.
6. Record laboratory measurements in **Quality & Treatment**. No gas becomes qualified automatically.
7. Add verified GPS coordinates if available; do not treat simulation as live GPS.

### Boundaries and limitations
This is educational simulation software, not an operational SF₆ handling, pressure, transport or safety system. Bay masses, recovery efficiency, and filling capacities are example inputs. Do not apply them to real GIS without OEM, site, and regulatory verification. No hardware interface or live location feed is connected. Local SQLite works for a single demonstration. On free hosting, local files can be ephemeral and shared visitors can modify the demo state: use a hosted database and authentication for production.
''')
    st.subheader('Export database tables')
    for t in ['bays','cylinders','vehicles','movements','vehicle_events','quality_tests','gps_logs']:
        st.download_button(f'Download {t}.csv',df(t).to_csv(index=False).encode('utf-8-sig'),f'{t}.csv','text/csv',key='download_'+t)
    st.divider()
    st.warning('Resetting replaces all demo transactions and typed test/GPS observations with the original scenario. Do this only when no one needs the demo history.')
    confirm=st.checkbox('I understand the demo data will be reset')
    if st.button('Reset to original scenario',disabled=not confirm):
        reset_demo(); st.success('Demo reset'); st.rerun()

st.sidebar.divider()
st.sidebar.caption('Source of truth: demo SQLite event log · UTC timestamps · Not a live tracking system')
