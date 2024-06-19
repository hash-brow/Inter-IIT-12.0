import csv
import calendar
import datetime

def temp_files():
    schedule = []

    with open(r'staticFiles/uploads/SCH.csv', 'r') as f:
        reader = csv.reader(f)
        header = next(reader)

        for row in reader:
            schedule.append(row)

    # 0 - ScheduleID
    # 1 - ScheduleId
    # 3 - Dep_Key
    # 7 - DepartureDateTime
    # 8 - ArrivalDateTime
    # 5 - DepartureAirport
    # 6 - ArrivalAirport
    # 9 - DepartureAirport
    # 10- ArrivalAirport
    # 16- FirstClass
    # 17- BusinessClass
    # 18- PremiumEconomyClass
    # 19- EconomyClass    
    # Arrival Time
            
    inventory = []

    with open(r'staticFiles/uploads/INV.csv', 'r') as f:
        reader = csv.reader(f)
        header = next(reader)

        for row in reader:
            inventory.append(row)

    flights = []

    idx = 0
    d_key = dict()

    for flight in inventory:
        schedule_id = flight[1]
        dep_key = flight[3][:-2]
        dept_time = flight[7]
        arr_time = flight[8]
        dept_airport = flight[9]
        arr_airport = flight[10]
        fc = int(flight[16])
        bc = int(flight[17])
        pec = int(flight[18])
        ec = int(flight[19])

        dep_epoch = calendar.timegm(datetime.datetime.strptime(dept_time, "%Y-%m-%d %H:%M:%S").timetuple())
        arr_epoch = calendar.timegm(datetime.datetime.strptime(arr_time, "%Y-%m-%d %H:%M:%S").timetuple())

        # print(dep_key)

        flights.append([idx, dep_key, dept_airport, arr_airport, 'FC', fc, dep_epoch, arr_epoch])
        d_key[(dep_key, 'FirstClass')] = idx
        idx += 1
        flights.append([idx, dep_key, dept_airport, arr_airport, 'BC', bc, dep_epoch, arr_epoch])
        d_key[(dep_key, 'BusinessClass')] = idx
        idx += 1
        flights.append([idx, dep_key, dept_airport, arr_airport, 'PC', pec, dep_epoch, arr_epoch])
        d_key[(dep_key, 'PremiumEconomyClass')] = idx
        idx += 1
        flights.append([idx, dep_key, dept_airport, arr_airport, 'EC', ec, dep_epoch, arr_epoch])
        d_key[(dep_key, 'EconomyClass')] = idx
        idx += 1

    with open(r'staticFiles/uploads/flights.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['UID', 'KEY', 'DEP', 'ARR', 'CLASS', 'CAPACITY', 'DEP_TIME', 'ARR_TIME'])
        writer.writerows(flights)

    pnr_data = []

    with open(r'staticFiles/uploads/PNRB.csv', 'r') as f:
        reader = csv.reader(f)
        header = next(reader)

        for row in reader:
            pnr_data.append(row)

    #0 - RECLOC,
    #2 - DEP_KEY,
    #3 - ACTION_CD
    #4 - COS_CD,
    #7 - PAX_FF_NUMCNT,
    #10- ORIG_CD,
    #11- DEST_CD,
    #13- DEP_DTML,
    #14- ARR_DTML
            
    passenger_data = []

    with open(r'staticFiles/uploads/PNRP.csv', 'r') as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            passenger_data.append(row)

    # 0 - RECLOC,
    # 11- SPECIAL_NAME_CD2
    # 12- SSR_CODE_CD1
    # 13- SPECIAL_NAME_CD1
    # 15- TierLevel
            
    rules = dict()

    with open(r'staticFiles/uploads/RULES.csv', 'r') as f:
        reader = csv.reader(f)
        header = next(reader)

        for row in reader:
            rules[row[0]] = [int(row[1]), int(row[2] == 'True')]

    final_data = []
    # Columns for final data
    # 0 - Index
    # 1 - PNR - from PNRB
    # 2 - Departure Key - from PNRB
    # 3 - Number of Passengers - from PAX CNT
    # 4 - PNR Score - from business rules and PNRP
    # 5 - Force Kickout - 0 / 1

    cnt = 0
    idx = 0

    for travel in pnr_data:
        pnr_number = travel[0]
        dep_key = travel[2]
        action_cd = travel[3]
        flightclass = travel[4]
        pax_cnt = int(travel[7])
        dept_airport = travel[10]
        arr_airport = travel[11]
        dept_time = travel[13]
        arr_time = travel[14]
        fc = 1

        if pax_cnt > 1:
            fc = 0

        score = 0

        while cnt < len(passenger_data) and passenger_data[cnt][0] == pnr_number:

            # update score here
            if passenger_data[cnt][11] in rules.keys():
                score += rules[passenger_data[cnt][11]][0]
                fc = min(fc, rules[passenger_data[cnt][11]][1])

            if passenger_data[cnt][12] in rules.keys():
                score += rules[passenger_data[cnt][12]][0]
                fc = min(fc, rules[passenger_data[cnt][12]][1])
            
            if passenger_data[cnt][13] in rules.keys():
                score += rules[passenger_data[cnt][13]][0]
                fc = min(fc, rules[passenger_data[cnt][13]][1])
            
            if passenger_data[cnt][15] in rules.keys():
                score += rules[passenger_data[cnt][15]][0]
                fc = min(fc, rules[passenger_data[cnt][15]][1])

            # score += rules[passenger_data[cnt][11]][0] + rules[passenger_data[cnt][12]][1] + rules[passenger_data[cnt][13]][0] + rules[passenger_data[cnt][15]][0]
            score += rules['PAX'][0]

            # update fc here
            # fc = min(fc, rules[passenger_data[cnt][11]][1], rules[passenger_data[cnt][12]][1], rules[passenger_data[cnt][13]][1], rules[passenger_data[cnt][15]][1])

            cnt += 1

        # score += rules[action_cd][0]
        if action_cd in rules.keys():
            score += rules[action_cd][0]
            fc = min(fc, rules[action_cd][1])
        
        score += rules[flightclass][0]

        fc = min(fc, rules[flightclass][1])

        final_data.append([idx, pnr_number, dep_key, pax_cnt, score, fc, d_key[(dep_key, flightclass)]])
        idx += 1

    with open(r'staticFiles/uploads/pnr_score.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['IDX','PNR', 'KEY', 'CNT', 'SCORE', 'FK', 'UID'])
        writer.writerows(final_data)
