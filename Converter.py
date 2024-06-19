import csv
def main2(flights_cancelled):
    # flights_cancelled = ['ZZ20240505AMDHYD2223', 'ZZ20240623GAUPNQ3440']  
    # with open("flights_cancelled.csv", 'r') as f:
    #     csvreader = csv.reader(f)
    #     fields = next(csvreader)
    #     for row in csvreader:
    #         flights_cancelled.append(row[0])
    pnr_data = dict()
    with open(r'staticFiles/uploads/pnr_score.csv', 'r') as f:
        csvreader = csv.reader(f)
        # fields = next(csvreader)
        for row in csvreader:
            # pnr_data.append(row)
            pnr_data[row[0]] = row[1:]


    flights = dict()
    with open(r'staticFiles/uploads/flights.csv', 'r') as f:
        csvreader = csv.reader(f)
        # fields = next(csvreader)
        for row in csvreader:
            # flights.append(row)
            flights[row[0]] = row[1:]

    for flight in flights_cancelled:
        for sol in range(10):
            default = "./output/" + str(sol) + "_" +  str(flight) + "_default.csv"
            final_data = []
            with open(default, 'r') as f:
                csvreader = csv.reader(f)
                # fields = next(csvreader)
                for row in csvreader:
                    # print(len(pnr_data))
                    idx = row[0]
                    len1 = int(row[1])
                    uids = row[2:]

                    temp = [pnr_data[idx][0], len1]

                    for uid in uids:
                        temp.append([flights[uid][0], flights[uid][3]])

                    final_data.append(temp)

            with open(default, 'w', newline='') as f:
                csvwriter = csv.writer(f)

                csvwriter.writerows(final_data)


            exception = "./output/" + str(sol) + "_" + str(flight) + "_exception.csv"
            final_data = []
            with open(exception, 'r') as f:
                csvreader = csv.reader(f)
                # fields = next(csvreader)
                for row in csvreader:
                    idx = row[0]
                    len1 = int(row[1])
                    uids = row[2:]

                    temp = [pnr_data[idx][0], len1]

                    for uid in uids:
                        temp.append([flights[uid][0], flights[uid][3]])

                    final_data.append(temp)

            with open(exception, 'w', newline='') as f:
                csvwriter = csv.writer(f)

                csvwriter.writerows(final_data)

# if __name__ == "__main__":
#     main2()
