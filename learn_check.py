#! /usr/bin/python3.5
from threading import *
from datetime import datetime
from influxdb import InfluxDBClient
from bcpme import *
import copy

results = {}
avgs = {}
maxs = {}
mins = {}
i = 0
results_lock = Lock()
interr = False


def fetcher(reg_list):
    if len(reg_list) == 0:
        log_danger("No measure to fetcher")
        return
    bcpmes = init_all_devices()
    if len(bcpmes) == 0:
        log_danger("No BCPME device configured")
        return
    db_name = "bcpme_measurements"
    client = InfluxDBClient(
        host='localhost',  # TODO change with the real address
        port=8086,  # TODO change with the real port
        database=db_name
    )
    client.create_database(db_name)
    for bcpme in bcpmes:
        results[bcpme.name] = {}
        results[bcpme.name] = {}

    def operation(measure_name, reg):
        size = reg["size"]
        for bcpme in bcpmes:
            # log("BCPME: %s  Fetching: %s" % (bcpme.name, measure_name), date=True)
            if size == 16:
                res = bcpme.big_request_16(reg["values"], num_registers, reg["scale"])
            elif size == 32:
                res = bcpme.big_request_32(reg["values"], num_registers, reg["scale"])
            else:
                continue

            for unit_id in res:
                for virtual in res[unit_id]:
                    val = res[unit_id][virtual]
                    if val != 0:
                        dev_name = bcpme.get_name_from_virtual(unit_id, virtual)
                        if measure_name not in results[bcpme.name]:
                            results[bcpme.name][measure_name] = {}
                        dev_id = dev_name["name"] + "_" + str(dev_name["phase"])
                        if dev_id not in results[bcpme.name][measure_name]:
                            results[bcpme.name][measure_name][dev_id] = []
                        results[bcpme.name][measure_name][dev_id].append(val)
                        data = [{
                            "measurement": measure_name,
                            "tags": {
                                "dev_name": dev_name["name"],
                                "phase": dev_name["phase"],
                                "bcpme_name": bcpme.name,
                            },
                            "time": datetime.utcnow(),
                            "fields": {
                                "value": val
                            }
                        }]
                        client.write_points(data)

    while True:
        global i
        i += 1
        for phase in reg_list:
            num_registers = reg_list[phase]["num_registers"]
            threads = []
            for in_measure_name in reg_list[phase]:
                if in_measure_name == "num_registers":
                    continue
                th = Thread(target=operation, args=(in_measure_name, reg_list[phase][in_measure_name]))
                threads.append(th)
            results_lock.acquire()
            for th in threads:
                th.start()
            for th in threads:
                th.join()
            results_lock.release()


def learner(to_learn):
    if to_learn is None:
        to_learn = []
    if len(to_learn) == 0:
        log_danger("Nothing to learn, pass a list with the name of measurement to learn")
        return
    length = 120
    discount_factor = .8
    while not interr:
        results_lock.acquire()
        tmp = copy.deepcopy(results)
        results_lock.release()
        for bcpme_name in tmp:
            if bcpme_name not in maxs:
                maxs[bcpme_name] = {}
            if bcpme_name not in mins:
                mins[bcpme_name] = {}
            if bcpme_name not in avgs:
                avgs[bcpme_name] = {}
            for measure in tmp[bcpme_name]:
                if measure in to_learn:
                    if measure not in maxs[bcpme_name]:
                        maxs[bcpme_name][measure] = {}
                    if measure not in mins[bcpme_name]:
                        mins[bcpme_name][measure] = {}
                    if measure not in avgs[bcpme_name]:
                        avgs[bcpme_name][measure] = {}
                    for dev_name in tmp[bcpme_name][measure]:
                        vals = tmp[bcpme_name][measure][dev_name]
                        val = vals[len(vals) - 1]
                        if dev_name not in maxs[bcpme_name][measure]:
                            maxs[bcpme_name][measure][dev_name] = val
                        if dev_name not in mins[bcpme_name][measure]:
                            mins[bcpme_name][measure][dev_name] = val
                        if val > maxs[bcpme_name][measure][dev_name]:
                            maxs[bcpme_name][measure][dev_name] = val
                        elif val < mins[bcpme_name][measure][dev_name]:
                            mins[bcpme_name][measure][dev_name] = val
                        avg = sum(vals) / float(len(vals))
                        avgs[bcpme_name][measure][dev_name] = avg


def checker(to_measure=None):
    if to_measure is None:
        to_measure = []
    if len(to_measure) == 0:
        log_danger("Nothing to check, pass a list with the name of measurement to check")
        return
    warn_threshold = .1
    dang_threshold = .15
    fmt = "%5s%8s%7s%15s%10s%15s%15s"
    header = "measure: [%s]\n" + fmt % (
    "BCPME", "name", "phase", "actual value", "average", "all time max", "all time low")
    while not interr:
        local_avg = avgs
        if local_avg != {}:
            os.system('cls||clear')
            log("Total values: " + str(i), date=True)
            for bcpme_name in local_avg:
                for measure in local_avg[bcpme_name]:
                    if measure in to_measure:
                        log(header % measure)
                        for dev_name in local_avg[bcpme_name][measure]:
                            values = results[bcpme_name][measure][dev_name]
                            val = values[len(values) - 1]
                            avg = local_avg[bcpme_name][measure][dev_name]
                            nmin = mins[bcpme_name][measure][dev_name]
                            nmax = maxs[bcpme_name][measure][dev_name]
                            warning_zone = avg * warn_threshold
                            danger_zone = avg * dang_threshold
                            name, phase = str(dev_name).split("_")
                            if val < avg - danger_zone or val > avg + danger_zone:
                                log_danger(
                                    fmt % (bcpme_name, name, phase, ("%2.2f" % val), ("%2.2f" % avg), ("%2.2f" % nmax),
                                           ("%2.2f" % nmin)))
                            elif val < avg - warning_zone or val > avg + warning_zone:
                                log_warning(
                                    fmt % (bcpme_name, name, phase, ("%2.2f" % val), ("%2.2f" % avg), ("%2.2f" % nmax),
                                           ("%2.2f" % nmin)))
                            else:
                                log_nominal(
                                    fmt % (bcpme_name, name, phase, ("%2.2f" % val), ("%2.2f" % avg), ("%2.2f" % nmax),
                                           ("%2.2f" % nmin)))

            sys.stdout.write(RESET)
            print("", end="\r")
        time.sleep(2)


if __name__ == "__main__":
    config = get_register_map()
    in_reg_list = {
        1: {
            "num_registers": config["registers"]["1"]["num_registers"],
            "current": config["registers"]["1"]["current"]
        }
    }
    to_learn_and_check = [
        "current"
    ]
    learner_th = Thread(target=learner, daemon=True, args=(to_learn_and_check,), name="learner")
    checker_th = Thread(target=checker, daemon=True, args=(to_learn_and_check,), name="checker")
    try:
        learner_th.start()
        checker_th.start()
        fetcher(in_reg_list)
    except KeyboardInterrupt:
        log_danger("Closed By Keyboard, please wait closing threads...")
        interr = True
        exit()
