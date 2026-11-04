# Seat sensor bench and ride tests

These tests give the paper real data for sir's Concern 1 (FSR under foam: calibration, hysteresis, creep, vibration) and Concern 2 (seat probe vs cabin probe in a hot cabin). Each test writes one CSV. Send me every CSV, the notes file and a few photos of the setup.

## 1. Parts

1. ESP32 DevKit V1 and its USB cable
2. FSR 402 (or 406), one 10 kΩ resistor
3. Two DS18B20 probes (the waterproof, metal-tip type is easiest), one 4.7 kΩ resistor
4. Optional: MPU6050 accelerometer board (only for the ride test)
5. A real seat cushion with polyurethane foam and fabric cover (car seat, office chair or a bus-style cushion), a flat rigid board under it (plywood or a thick book)
6. A flat piece of cardboard about 20 x 20 cm to spread the weights
7. Loads: 1 L water bottles (1 kg each), a bucket or bag to hold them, a bathroom scale to weigh people and loads
8. Breadboard and jumper wires, tape

## 2. Wiring

1. FSR: one leg to 3.3V, other leg to GPIO34. 10 kΩ from GPIO34 to GND.
2. DS18B20 (both probes in parallel): red to 3.3V, black to GND, yellow (data) to GPIO18. One 4.7 kΩ from GPIO18 to 3.3V.
3. MPU6050 (optional): VCC to 3.3V, GND to GND, SDA to GPIO21, SCL to GPIO22.
4. Placement:
   1. FSR flat on the rigid board, foam cushion on top, cover on top of the foam.
   2. Probe A (seat probe): taped on top of the foam, under the seat cover, right under where the thigh rests.
   3. Probe B (cabin probe): hanging in free air about 30 cm from the seat, in the shade, touching nothing.
   4. MPU6050: taped firmly to the seat frame, not the foam.
5. Which probe is A: after uploading, hold one probe in your fist for 20 s and watch the serial output. The column that rises is that probe. If the hand probe shows up as t_b, swap the labels in your notes (tell me which is which).

## 3. Upload the logger sketch

Arduino IDE:

1. Boards Manager: install "esp32 by Espressif Systems".
2. Library Manager: install "OneWire" (Paul Stoffregen) and "DallasTemperature" (Miles Burton).
3. Open `seat_logger/seat_logger.ino`, board "ESP32 Dev Module", pick the port, Upload.
4. Open Serial Monitor at 115200 once to check you see lines like `1234,0,0,0.0,...`. The first line says `# probes=2 mpu=1` (mpu=0 is fine if you have no MPU6050). Close Serial Monitor before logging, or the port stays busy.

Or arduino-cli:

```
arduino-cli core install esp32:esp32
arduino-cli lib install OneWire DallasTemperature
arduino-cli compile --fqbn esp32:esp32:esp32 seat_logger
arduino-cli upload --fqbn esp32:esp32:esp32 -p COM5 seat_logger
```

(Use your port: `COM5` on Windows, `/dev/ttyUSB0` on Linux, `/dev/cu.usbserial-XXXX` on Mac.)

## 4. Logging on the laptop

```
pip install pyserial
python -m serial.tools.list_ports
python log_serial.py --port COM5 --out test1_calibration.csv
```

While it runs, type a label and press Enter whenever the situation changes (for example `load_10kg`, `sit`, `bag_sun`). Every row after that carries the label. Type `q` and Enter to stop and save. Labels must be typed at the moment the change happens, so keep the laptop next to you.

## 5. Tests

Test 0, noise floor (2 min). Empty seat, nobody touching anything. Label `empty`. File `test0_noise.csv`.

Test 1, static calibration through foam (about 30 min). File `test1_calibration.csv`.

1. Put the cardboard on the seat. Label `load_0kg`, wait 20 s.
2. Add load in steps, putting bottles in the bucket on the cardboard: 1, 2, 5, 10, 15, 20, 30 kg. Before each step type the label (`load_5kg`), place the load gently, wait 20 s.
3. Then people of known weight sitting normally, feet on the floor: label `person_62kg` (use their real weight from the scale), sit still 20 s. Get as many different weights as you can between 40 and 100 kg.
4. Come back down in the same steps with labels `down_30kg`, `down_20kg` and so on, to `down_0kg`.
5. Do steps 1 to 4 three times. Label the rounds `r1_load_5kg`, `r2_load_5kg`, ... so I can measure repeatability.

Test 2, creep (10 min). One person sits still for 10 minutes. Label `creep_<weight>kg`. Then stands up, label `release`, wait 2 min. File `test2_creep.csv`.

Test 3, posture (5 min). Same person, 30 s each: `pos_center`, `pos_front_edge`, `pos_left`, `pos_right`, `pos_leaning_back`, `pos_cross_legged`. File `test3_posture.csv`. This shows whether one small FSR misses people who sit off-centre.

Test 4, thermal at room temperature (about 45 min). File `test4_thermal_room.csv`.

1. `empty` 3 min.
2. `sit` 10 min (person sits still).
3. `after_stand` 5 min (person stands up and walks away).
4. `bag_room` 10 min (a bag that has been indoors, around 3 kg).
5. `bag_sun` 10 min (the same bag after 20 min in direct sun, placed on the seat right away).
6. `laptop_on` 10 min (a running laptop on the seat), optional.

Test 5, thermal in a hot car (about 40 min, do it on a sunny afternoon). Park in direct sun with windows closed for 30 min first so the cabin heats up. File `test5_thermal_hotcar.csv`. Same sequence as Test 4 inside the car, but with the cabin probe hanging in the car, and with door open breaks between steps. Safety first: never stay inside a hot car longer than 10 minutes at a time, keep water with you, keep a door open between steps, and stop at once if anyone feels dizzy or unwell. Skip the `sit` step if the cabin is above 45 °C.

Test 6, ride vibration (30 min). Put the cushion with the FSR on a passenger seat of a car (or your seat on a bus or auto), MPU6050 taped to the seat frame, laptop logging. File `test6_ride.csv`.

1. `ride_empty` 10 min with nobody on the cushion.
2. `ride_bag` 5 min with the bag on it.
3. `ride_seated` 10 min with a person sitting.
4. Type `bump` or `pothole` the moment the vehicle hits one, then the previous label again.
5. Choose a route with a few speed breakers and rough patches. Someone else should drive.

## 6. Notes file

Write `notes.txt` with:

1. FSR model (402, 406 or other), resistor values actually used
2. Cushion: what it is, foam thickness in cm, cover material
3. Weights of everyone who sat, and of the bag
4. Room temperature, and the car cabin temperature at the start of Test 5
5. Vehicle and road type for Test 6
6. Which probe was A (seat) and which was B (cabin)
7. Anything that went wrong or looked strange

## 7. Photos

1. The wiring on the breadboard
2. FSR placed on the board, and the cushion on top
3. The seat probe under the cover and the cabin probe hanging
4. The setup in the car for Tests 5 and 6

Send all CSVs, `notes.txt` and photos here. I will turn them into the calibration curve, hysteresis and creep numbers, the noise-attenuation plot and the hot-cabin thermal plot for the paper.
