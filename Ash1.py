# todo: count cqm constraints, and if they exceed 100,000 ignore the default
# weight constraints (dwave max constraints = 100,000)
# todo: overbooking - if sub-class is overbooked but parent flight is not, we are not considering
# all fo's in the flight_options list, leading to a sub-optimal solution.
import dimod
from dwave.system import LeapHybridCQMSampler
from dwave.samplers import SteepestDescentSampler
import pandas as pd
import random
import csv

to_write_to_csv = 1

# default_constant = 1e8
# multi_leg_constant = 10
# infty_constant = 1e11
# class_constant = 5
mean_delay = 0
total_pnrs_assigned = 0

class FlightOption:
    def __init__(self, fid, dep_loc, arr_loc, dep_time, arr_time, fclass, capacity):
        self.fid = fid # unique id 
        self.dep_loc = dep_loc # departure location
        self.arr_loc = arr_loc # arrival location
        self.dep_time = dep_time # departure time (ignore date, say for eg. epoch value)
        self.arr_time = arr_time # arrival time (^^)
        self.fclass = fclass # class, 1 for first, 2 for business, 3 for PE, 4 for economy
        self.capacity = capacity # empty capacity in flight option

    def print(self):
        print(self.fid, self.dep_loc, self.arr_loc, self.dep_time, self.arr_time, self.fclass, self.capacity)

curr_pid = 0
class PNR:
    def __init__(self, pid, fo, score, cnt, multi_leg_constant, class_constant):
        self.pid = pid # pnr id
        self.fo = fo # original fo
        self.score = score # S_p
        self.cnt = cnt # pax cnt
        self.multi_leg_constant = multi_leg_constant
        self.class_constant = class_constant
        assert self.cnt > 0

    def get_m_value(self, route):
        flight_option = route.flight_options[-1]
        # global class_constant
        # global multi_leg_constant

        cavg = 0
        for each in route.flight_options:
            cavg += each.fclass
        cavg /= len(route.flight_options)

        ret = self.score * self.cnt * (flight_option.arr_time - self.fo.arr_time) * ( \
                1 + (cavg / (self.class_constant * self.fo.fclass))) * ( \
                1 + (len(route.flight_options) / self.multi_leg_constant))
        return ret

class Route:
    def __init__(self, rid, flight_options):
        self.rid = rid # route id   
        self.flight_options = flight_options # list of flight option objects making up the route,
        # for eg, if route is A->B->C, flight_options_list will have size 2, consisting of two flight options,
        # the first element corresponding to the FO corresponding to A->B, and the second element corresponding to the 
        # FO corresponding to B->C

    def print(self):
        for each in self.flight_options:
            each.print()

    def write_csv_debug(self, filename):
        if not to_write_to_csv:
            return
        with open(filename, "a", newline='') as f:
            csvwriter = csv.writer(f, delimiter=' ')
            csvwriter.writerow([len(self.flight_options)] + [fo.fid for fo in self.flight_options])

number_of_routes = 0

class Graph:
    def __init__(self, flight_options_list, downline, Max_departure_delay, Min_layover_time, Max_layover_time):
        self.graph = {}
        self.downline = downline
        self.Max_departure_delay = Max_departure_delay
        self.Min_layover_time = Min_layover_time
        self.Max_layover_time = Max_layover_time

        for flight_option in flight_options_list:
            self.add_edge(flight_option.dep_loc, flight_option.arr_loc, flight_option.fid, flight_option.fclass, flight_option.capacity, flight_option.dep_time, flight_option.arr_time)

    def add_edge(self, dep_loc, arr_loc, fid, fclass, capacity, dep_time, arr_time):
        if dep_loc not in self.graph:
            self.graph[dep_loc] = []
        self.graph[dep_loc].append([arr_loc, fid, fclass, capacity, dep_time, arr_time])

    def find_all_paths_helper(self, source, arr_time, destination, path, is_first_flight):
        if source == destination:
            return [path]

        if len(path) >= int(self.downline):
            return []

        paths = []

        if source not in self.graph: return paths

        for edge in self.graph[source]:
            node = edge[0]

            if (not is_first_flight and (edge[4] >= arr_time + int(self.Min_layover_time) and edge[4] <= arr_time + int(self.Max_layover_time))) \
                or (is_first_flight and edge[4] <= arr_time + int(self.Max_departure_delay) and edge[4] >= arr_time):
                new_path = path.copy()
                new_path.append(FlightOption(edge[1], source, node, edge[4], edge[5], edge[2], edge[3]))
                paths += self.find_all_paths_helper(node, edge[5], destination, new_path, 0)

        return paths

    def find_all_paths(self, source, arr_time, destination):
        paths =  self.find_all_paths_helper(source, arr_time, destination, [], 1)
        routes = []

        for path in paths:
            global number_of_routes
            routes.append(Route(number_of_routes, path))
            number_of_routes += 1
        
        return routes

def generateRoutes(F, FOC, downline, Max_departure_delay, Min_layover_time, Max_layover_time):
    G = Graph(F, downline, Max_departure_delay, Min_layover_time, Max_layover_time)
    routes = []

    source = FOC.dep_loc
    destination = FOC.arr_loc

    # find all routes from source to destination
    routes = G.find_all_paths(source, FOC.dep_time, destination)

    return routes

class pnr_flight_matrix:
    def __init__(self, pfid, pnr_list, route_list, infty, default_constant):
        self.pfid = pfid
        self.pnr_list = pnr_list
        self.route_list = route_list
        self.infty = infty
        self.default_constant = default_constant

        self.pnr_sz = len(pnr_list)
        assert self.pnr_sz > 0
        self.rl_sz = len(route_list) + 1
        self.M = [[p.get_m_value(r) for r in route_list] + [p.score * infty] for p in pnr_list] 
        self.X = [[dimod.Binary(str(pfid) + '|' + str(i) + '|' + str(j)) for j in range(self.rl_sz)] for i in range(self.pnr_sz)]
        self.XS = [[0 for _ in range(self.rl_sz)] for _ in range(self.pnr_sz)] # sampled X

        # prioritising for default solution
        self.D = [dimod.Binary(str(pfid) + 'D' + str(i)) for i in range(self.rl_sz - 1)]
        self.Y = [dimod.quicksum((self.X[j][i] * self.pnr_list[j].cnt) for j in range(self.pnr_sz)) for i in range(self.rl_sz)]

        self.DS = [0 for _ in range(self.rl_sz - 1)]
        self.YS = [0 for _ in range(self.rl_sz)]

    def add_default_constraints(self, cqm):
        cnst = dimod.quicksum(self.D[i] for i in range(self.rl_sz - 1))
        if self.rl_sz > 1:
            cqm.add_constraint(cnst == 1)

    # always call generate_XS first
    def generate_DS_YS(self, sample): 
        for i in range(self.rl_sz - 1):
            self.DS[i] = sample[str(self.pfid) + 'D' + str(i)]
        for i in range(self.rl_sz):
            self.YS[i] = sum((self.XS[j][i] * self.pnr_list[j].cnt) for j in range(self.pnr_sz))

    def add_row_constraints(self, cqm):
        for i in range(self.pnr_sz):
            constraint = dimod.quicksum(self.X[i][j] for j in range(self.rl_sz))
            cqm.add_constraint(constraint == 1)

    def get_col_constraints(self):
        ret = dict()
        for i in range(self.rl_sz - 1):
            constraint = dimod.quicksum((self.X[j][i] * self.pnr_list[j].cnt) for j in range(self.pnr_sz))
            for f in self.route_list[i].flight_options:
                if f.fid not in ret:
                    ret[f.fid] = 0
                ret[f.fid] += constraint
        return ret

    def get_objective(self):
        ret = 0
        for i in range(self.pnr_sz):
            for j in range(self.rl_sz):
                ret += self.X[i][j] * self.M[i][j]

        # global default_constant
        for i in range(self.rl_sz - 1):
            ret -= self.D[i] * self.Y[i] * self.default_constant

        return ret

    def generate_XS(self, sample):
        for i in range(self.pnr_sz):
            for j in range(self.rl_sz):
                self.XS[i][j] = sample[str(self.pfid) + '|' + str(i) + '|' + str(j)]

    def print_M(self):
        for i in range(self.pnr_sz):
            print(self.pnr_list[i].pid, end=' ')
            for j in range(self.rl_sz):
                print(self.M[i][j], end=' ')
            print('')

        print("D: ")
        print(self.DS)
        print("Y: ")
        print(self.YS)
        #print('\n'.join(['\t'.join([str(cell) for cell in row]) for row in self.M]))

    def print(self):
        print("\nPrinting output for PFID " + str(self.pfid)) 
        print("--------------------------")
        global mean_delay
        global total_pnrs_assigned
        for i in range(self.pnr_sz):
            print("\nPNR ID " + str(self.pnr_list[i].pid))
            fcnt = 0
            for j in range(self.rl_sz):
                fcnt += self.XS[i][j]

                if self.XS[i][j] != 0:
                    print("Original Route: ")
                    self.pnr_list[i].fo.print()
                    if j != (self.rl_sz - 1):
                        print("Assigned route " + str(j) + " with XS " + str(self.XS[i][j]) + " orig score " 
                                + str(self.pnr_list[i].score))
                        self.route_list[j].print()
                        mean_delay += self.route_list[j].flight_options[-1].arr_time - self.pnr_list[i].fo.arr_time
                        total_pnrs_assigned += self.pnr_list[i].cnt
                    else:
                        print("Not Assigned a Route! Orig score " + str(self.pnr_list[i].score))

            print("fcnt: " + str(fcnt))

    def write_csv(self, fnum):
        default = []
        exception = []

        for i in range(self.pnr_sz):
            for j in range(self.rl_sz):
                if self.XS[i][j] == 0: continue
                if j == (self.rl_sz - 1):
                    exception.append([self.pnr_list[i].pid, -1])
                    continue
                to_append = [self.pnr_list[i].pid, len(self.route_list[j].flight_options)]
                for each in self.route_list[j].flight_options:
                    to_append.append(each.fid)
                if self.DS[j] == 0:
                    exception.append(to_append)
                else:
                    default.append(to_append)

        with open("output/" + str(fnum) + "_default.csv", "w+", newline='') as fp:
            writer = csv.writer(fp, delimiter=",")
            writer.writerows(default)
        with open("output/" + str(fnum) + "_exception.csv", "w+", newline='') as fp:
            writer = csv.writer(fp, delimiter=",")
            writer.writerows(exception)

    def write_csv_debug(self, filename):
        if not to_write_to_csv:
            return
        with open(filename, "a", newline='') as f:
            csvwriter = csv.writer(f)
            for i in range(self.pnr_sz):
                for j in range(self.rl_sz):
                    if self.XS[i][j] == 0 or j == self.rl_sz - 1: continue
                    for fo in self.route_list[j].flight_options:
                        csvwriter.writerow([self.pnr_list[i].pid, fo.fid, self.pnr_list[i].score, self.pnr_list[i].cnt])

overbooked_ans = dict() 
def overbook_trim(plist, fid, capacity):
    tmp_list = []
    for each in plist:
        tmp_list.append([each.score, each])
    tmp_list.sort(key = lambda x: x[0])

    sz = len(plist)
    ret = []
    for i in range(sz - capacity):
        ret.append(tmp_list[i][1])

    for i in range(max(sz - capacity, 0), sz):  # max to deal with case when sz < capacity
        overbooked_ans[tmp_list[i][1].pid] = fid
    return ret

def main1(flights_cancelled, DwaveToken, downline, Max_departure_delay, Min_layover_time, Max_layover_time, multi_leg_constant, infty_constant, class_constant, default_constant):
    # flights_cancelled = ['ZZ20240505AMDHYD2223', 'ZZ20240623GAUPNQ3440']
    flights_ob = [] # overbooked flights

    pnrs = pd.read_csv("staticFiles/uploads/pnr_score.csv")
    seats_assigned = dict()
    pnr_map_tmp = dict()
    total_pnrs = 0
    total_impacted_pnrs = 0
    for index, row in pnrs.iterrows():
        total_pnrs += 1
        key = row['UID']
        cnt = row['CNT']
        if key in seats_assigned:
            seats_assigned[key] += cnt
        else:
            seats_assigned[key] = cnt

        if key not in pnr_map_tmp:
            pnr_map_tmp[key] = []
        pnr_map_tmp[key].append((row['IDX'], row['SCORE'], cnt))

    flights = pd.read_csv("staticFiles/uploads/flights.csv")
    flight_options = []                 # list of all non-impacted flight options
    flight_options_map = dict()         # map from fid to fo object 
    flight_constraints = dict()

    seats_assigned_flight = dict()  # seats assigned dict with fnum as key
    max_capacity = dict() # capacity of each flight, fnum is key
    for index, row in flights.iterrows():
        fnum = row['KEY']
        fid = row['UID']
        if fnum not in seats_assigned_flight: seats_assigned_flight[fnum] = 0
        seats_assigned_flight[fnum] += seats_assigned[fid]

        if seats_assigned[fid] > row['CAPACITY'] and fnum not in flights_cancelled:
            print("overbooked fnum " + str(fnum) + " sa " + str(seats_assigned[fid]) + " cap " + str(row['CAPACITY']) + " fid " + str(fid))
            flights_ob.append(fnum)
            flights_cancelled.append(fnum)

        if fnum not in max_capacity: max_capacity[fnum] = 0
        max_capacity[fnum] += row['CAPACITY']

    for key, val in seats_assigned_flight.items():
        if key in flights_cancelled: continue
        if val > max_capacity[key] and key not in flights_cancelled:
            flights_cancelled.append(key)
            flights_ob.append(key)

    # remove duplicated
    flights_ob = list(set(flights_ob))
    flights_cancelled = list(set(flights_cancelled))

    print("overbooked flight_ob " + str(len(flights_ob)))
    pnr_map = dict()

    # indices of impacted flight options
    fo_cnc_idx = []
    fo_ob_idx = []
    flights_cnc_idx = []
    flight_fid_map = dict() 
    for index, row in flights.iterrows():
        fid = row['UID']
        fnum = row['KEY']
        if fnum not in flights_cancelled: continue
        fo_cnc_idx.append(fid)
        if fnum in flights_ob: fo_ob_idx.append(fid)
        flights_cnc_idx.append(fnum)

        if fnum not in flight_fid_map: flight_fid_map[fnum] = []
        flight_fid_map[fnum].append(fid)

    for index, row in flights.iterrows():
        cabin_tp = 1
        cb = row['CLASS']
        if cb == "BC": cabin_tp = 2
        elif cb == "PC": cabin_tp = 3
        elif cb == "EC": cabin_tp = 4

        #flight_options.append(FlightOption(index, row['DepartureAirport'], row['ArrivalAirport'], row['DepartureEpoch'], row['ArrivalEpoch'], cabin_tp, row['Inventory']))
        fid = row['UID']
        fo = FlightOption(fid, row['DEP'], row['ARR'], row['DEP_TIME'], row['ARR_TIME'], cabin_tp, row['CAPACITY'] - seats_assigned[fid])

        flight_options_map[fid] = fo
        if fid not in fo_cnc_idx or fid in fo_ob_idx:
            flight_options.append(fo)

        if fid not in pnr_map:
            pnr_map[fid] = []

        for each in pnr_map_tmp[fid]:
            pnr_map[fid].append(PNR(each[0], fo, each[1], each[2], multi_leg_constant, class_constant)) 

    print("sz")
    print(len(flight_options))
    route_map = dict()
    for fnum in flights_cancelled:
        route_map[fnum] = generateRoutes(flight_options, flight_options_map[flight_fid_map[fnum][0]], downline, Max_departure_delay, Min_layover_time, Max_layover_time)
        for ro in route_map[fnum]:
            ro.write_csv_debug("staticFiles/uploads/routes.csv")
        print("fnum " + str(fnum) + " routes count " + str(len(route_map[fnum])))

    mlist = []
    #infty = 5000 * (48 * 60 * 60) * total_pnrs 
    #infty = 1e14
    # global infty_constant
    infty = infty_constant

    tmp_cnt = 0
    pfid_fnum_map = dict()
    for fnum in flights_cancelled:
        plist = []
        for fid in flight_fid_map[fnum]:
            plist += pnr_map[fid]

        """
        if fnum in flights_ob:
            for i in range(4):
                if len(plist) == 0: break
                fid = flight_fid_map[fnum][i]
                plist = overbook_trim(plist, fid, flight_options_map[fid].capacity + seats_assigned[fid])

        if len(plist) == 0: continue
        """
        mlist.append(pnr_flight_matrix(tmp_cnt, plist, route_map[fnum], infty, default_constant))
        pfid_fnum_map[tmp_cnt] = fnum

        for j in range(mlist[-1].pnr_sz):
            total_impacted_pnrs += mlist[-1].pnr_list[j].cnt

        tmp_cnt += 1

    cqm = dimod.ConstrainedQuadraticModel()
    net_obj = dimod.quicksum(each.get_objective() for each in mlist)
    cqm.set_objective(net_obj)
    for each in mlist:
        each.add_row_constraints(cqm)
        each.add_default_constraints(cqm)

        for key, val in each.get_col_constraints().items():
            if key in flight_constraints:
                flight_constraints[key] += val
            else:
                flight_constraints[key] = val

    fcnt = 0
    for key, val in flight_constraints.items():
        fcnt += 1
        cqm.add_constraint(val <= max(flight_options_map[key].capacity, 0))

    print(fcnt)
    sampler = LeapHybridCQMSampler(token=DwaveToken)

    sampleset = sampler.sample_cqm(cqm).aggregate()
    sampleset = sampleset.filter(lambda x: cqm.check_feasible(x.sample))

    # postprocessing
    #pp_sampler = SteepestDescentSampler()
    #sampleset = pp_sampler.sample(net_obj, initial_states=sampleset).aggregate()
    #sampleset = sampleset.filter(lambda x: cqm.check_feasible(x.sample))

    print('\nSolutions')
    print('---------')
    if len(sampleset) == 0:
        print('No feasible solution found.')
    else:
        sampleset = sampleset.truncate(10)
        global mean_delay
        global total_pnrs_assigned
        for index, sample in enumerate(sampleset.samples()):
            mean_delay = 0
            total_pnrs_assigned = 0
            #print(sample)
            print(f'{index + 1:}  ')
            print(f'Objective: '
                  f'{cqm.objective.energy(sample): 8.2f}, ', end='')
            print('')

            for each in mlist:
                each.generate_XS(sample)
                each.generate_DS_YS(sample)
                each.print()
                each.print_M()
                each.write_csv_debug("staticFiles/uploads/pnr_out.csv")
                each.write_csv(str(index) + "_" + pfid_fnum_map[each.pfid])

            if index == 0:
                tmp33 = [total_pnrs_assigned, total_impacted_pnrs, mean_delay/total_pnrs_assigned]
                with open("output/stats.csv", "w+") as fp:
                    csvwriter = csv.writer(fp)
                    csvwriter.writerow(["Total Passengers re-accommodated", "Total Impacted Passengers", "Mean Arrival Delay (s)"])
                    csvwriter.writerow(tmp33)

            print(str(total_pnrs_assigned) + " assigned out of " + str(total_impacted_pnrs))
            if total_pnrs_assigned > 0:
                print("Mean time delay: " + str(mean_delay / total_pnrs_assigned))

# if __name__ == '__main__':
#     main1()
