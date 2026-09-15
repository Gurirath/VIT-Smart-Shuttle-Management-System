import tkinter as tk
from tkinter import ttk
import math

PRESSURE_THRESHOLD=1200
HUMAN_TEMP_MIN=36.1
HUMAN_TEMP_MAX=37.2
START_LAT,START_LNG=12.9692,79.1559
END_LAT,END_LNG=12.9725,79.1630
MAX_PASSENGERS=30
FIRST_STUDENT_ID=21001
FARE_PER_KM=5.0
MINIMUM_FARE=2.0
LONG_PRESS_TIME=1.5
GPS_CHANGE_STEP=5

def distance_km(lat1,lon1,lat2,lon2):
    r=6371.0
    a=math.sin(math.radians(lat2-lat1)/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(math.radians(lon2-lon1)/2)**2
    return r*2*math.atan2(math.sqrt(a),math.sqrt(1-a))

class ShuttleGUI:
    def __init__(self,root):
        self.root=root; root.title('VIT Smart Shuttle System - Python GUI'); root.geometry('1150x760')
        self.pressure=tk.IntVar(value=0); self.gps=tk.IntVar(value=0); self.temp=tk.DoubleVar(value=36.7); self.wifi=tk.BooleanVar(value=True)
        self.seat=tk.StringVar(value='EMPTY'); self.route=tk.StringVar(value='0%'); self.location=tk.StringVar(value=f'{START_LAT:.6f}, {START_LNG:.6f}')
        self.net=tk.StringVar(value='WiFi ONLINE'); self.mqtt=tk.StringVar(value='MQTT ONLINE'); self.passengers_var=tk.StringVar(value='0 / 30'); self.free=tk.StringVar(value='30'); self.dist=tk.StringVar(value='0.00 km'); self.fare=tk.StringVar(value='₹0.00'); self.temp_disp=tk.StringVar(value='36.7 °C')
        self.current_lat=START_LAT; self.current_lng=START_LNG; self.prev_route=-1; self.people=[]; self.next_id=FIRST_STUDENT_ID
        self.build(); self.log('VIT SMART SHUTTLE SYSTEM'); self.log('Python GUI simulation ready.'); self.log('Short face scan = ENTRY | Long face scan = EXIT'); self.update()

    def build(self):
        ttk.Label(self.root,text='VIT SMART SHUTTLE SYSTEM',font=('Arial',22,'bold')).pack(pady=10)
        main=ttk.Frame(self.root,padding=10); main.pack(fill='both',expand=True); main.columnconfigure((0,1),weight=1); main.rowconfigure(1,weight=1)
        c=ttk.LabelFrame(main,text='Sensors & Controls',padding=10); c.grid(row=0,column=0,sticky='nsew',padx=5,pady=5)
        s=ttk.LabelFrame(main,text='Live Status',padding=10); s.grid(row=0,column=1,sticky='nsew',padx=5,pady=5)
        self.slider(c,'Seat Pressure (0-4095)',self.pressure,0,4095,0); self.slider(c,'GPS Position (0-100%)',self.gps,0,100,2); self.slider(c,'Temperature (°C)',self.temp,0,50,4)
        ttk.Checkbutton(c,text='WiFi Enabled',variable=self.wifi,command=self.toggle_wifi).grid(row=6,column=0,sticky='w',pady=8)
        f=ttk.Frame(c); f.grid(row=7,column=0,columnspan=2,sticky='ew'); ttk.Button(f,text='FACE SCAN\nENTRY',command=self.entry).pack(side='left',fill='x',expand=True,padx=3); ttk.Button(f,text='FACE SCAN\nEXIT',command=self.exit).pack(side='left',fill='x',expand=True,padx=3)
        items=[('Seat',self.seat),('Temperature',self.temp_disp),('Route',self.route),('Location',self.location),('Passengers',self.passengers_var),('Seats free',self.free),('Network',self.net),('MQTT',self.mqtt),('Last distance',self.dist),('Last fare',self.fare)]
        for i,(name,var) in enumerate(items): ttk.Label(s,text=name+':',font=('Arial',10,'bold')).grid(row=i,column=0,sticky='w',pady=3); ttk.Label(s,textvariable=var).grid(row=i,column=1,sticky='w',padx=12)
        lf=ttk.LabelFrame(main,text='System / MQTT Log',padding=5); lf.grid(row=1,column=0,columnspan=2,sticky='nsew',pady=5); self.text=tk.Text(lf,font=('Consolas',10)); self.text.pack(fill='both',expand=True)

    def slider(self,parent,label,var,a,b,row):
        ttk.Label(parent,text=label).grid(row=row,column=0,sticky='w',pady=(5,0)); ttk.Scale(parent,from_=a,to=b,variable=var,command=lambda _:None).grid(row=row+1,column=0,sticky='ew'); ttk.Label(parent,textvariable=var).grid(row=row+1,column=1,padx=8); parent.columnconfigure(0,weight=1)

    def log(self,msg): self.text.insert('end',msg+'\n'); self.text.see('end')

    def publish(self,topic,payload): self.log(f"[{'MQTT' if self.wifi.get() else 'GSM FALLBACK'}] {topic} -> {payload}")

    def toggle_wifi(self):
        if self.wifi.get(): self.net.set('WiFi ONLINE'); self.mqtt.set('MQTT ONLINE'); self.log('[NETWORK] WiFi ONLINE / MQTT ONLINE / NORMAL')
        else: self.net.set('WiFi OFFLINE'); self.mqtt.set('MQTT OFFLINE'); self.log('[NETWORK] WiFi OFFLINE / MQTT OFFLINE / GSM FALLBACK')

    def update_gps(self):
        ratio=self.gps.get()/100.0; self.current_lat=START_LAT+ratio*(END_LAT-START_LAT); self.current_lng=START_LNG+ratio*(END_LNG-START_LNG); p=int(round(ratio*100)); self.route.set(f'{p}%'); self.location.set(f'{self.current_lat:.6f}, {self.current_lng:.6f}')
        if self.prev_route<0 or abs(p-self.prev_route)>=GPS_CHANGE_STEP:
            self.prev_route=p; self.log(f'[GPS EVENT] {self.location.get()} | Route {p}%'); self.publish('vit/shuttle1/gps',f'{self.current_lat:.6f},{self.current_lng:.6f}')

    def update_seat(self):
        p=self.pressure.get(); t=float(self.temp.get()); old=self.seat.get(); new='EMPTY' if p<PRESSURE_THRESHOLD else ('STUDENT' if HUMAN_TEMP_MIN<=t<=HUMAN_TEMP_MAX else 'BAG'); self.seat.set(new); self.temp_disp.set(f'{t:.1f} °C')
        if new!=old:
            self.log(f'[SEAT] State={new}, Pressure={p}, Temperature={t:.1f} C'); self.publish('vit/shuttle1/seat',f'{new},TEMP={t:.1f},PRESSURE={p}')

    def entry(self):
        if len(self.people)>=MAX_PASSENGERS: self.log('[ENTRY DENIED] SHUTTLE FULL'); return
        pid=self.next_id; self.next_id+=1; self.people.append((pid,self.current_lat,self.current_lng)); self.log(f'[ENTRY] Face VERIFIED | VIT{pid} | {self.current_lat:.6f},{self.current_lng:.6f}'); self.publish('vit/shuttle1/billing',f'ENTRY,VIT{pid},{self.current_lat:.6f},{self.current_lng:.6f}'); self.refresh_people()

    def exit(self):
        if not self.people: self.log('[EXIT DENIED] NO PASSENGERS'); return
        pid,lat,lng=self.people.pop(); d=distance_km(lat,lng,self.current_lat,self.current_lng); f=max(MINIMUM_FARE,d*FARE_PER_KM); self.dist.set(f'{d:.2f} km'); self.fare.set(f'₹{f:.2f}'); self.log(f'[TRIP COMPLETED] VIT{pid} | Distance={d:.2f} km | Fare=Rs {f:.2f}'); self.publish('vit/shuttle1/billing',f'EXIT,VIT{pid},{d:.2f}km,Rs{f:.2f}'); self.refresh_people()

    def refresh_people(self): self.passengers_var.set(f'{len(self.people)} / {MAX_PASSENGERS}'); self.free.set(str(MAX_PASSENGERS-len(self.people)))

    def update(self): self.update_gps(); self.update_seat(); self.refresh_people(); self.root.after(500,self.update)

if __name__=='__main__':
    root=tk.Tk(); ShuttleGUI(root); root.mainloop()
