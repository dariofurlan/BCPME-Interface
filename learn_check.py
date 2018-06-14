#! /usr/bin/python3.5
import json
import os
import sys
from threading import *
import time
from datetime import datetime
from influxdb import InfluxDBClient
from bcpme import BCPME, Terminal, init_all_devices

values = {}
averages = {}
maxs = {}
mins = {}
i = 0


def fetcher(reg_list):
    if len(reg_list) == 0:
        Terminal.log_danger("No measure to fetcher")
        return
    bcpmes = init_all_devices()
    if len(bcpmes) == 0:
        Terminal.log_danger("No BCPME device configured")
        return
    db_name = "bcpme_measurements"
    client = InfluxDBClient(
        host='localhost',  # TODO change with the real address
        port=8086,  # TODO change with the real port
        database=db_name
    )
    client.create_database(db_name)

    def operation(measure_name, reg):
        size = reg["size"]
        for bcpme in bcpmes:
            lock.acquire()
            Terminal.log("BCPME: %s  Fetching: %s" % (bcpme.name, measure_name), date=True)
            if size == 16:
                res = bcpme.big_request_16(reg["values"], num_registers, reg["scale"])
            elif size == 32:
                res = bcpme.big_request_32(reg["values"], num_registers, reg["scale"])
            else:
                lock.release()
                continue
            lock.release()
            for unit_id in res:
                for virtual in res[unit_id]:
                    val = res[unit_id][virtual]
                    if val != 0:
                        dev_name = bcpme.get_name_from_virtual(unit_id, virtual)
                        data = [{
                            "measurement": measure_name,
                            "tags": {
                                "dev_name": dev_name["name"],
                                "bcpme_name": bcpme.name,
                            },
                            "time": datetime.utcnow(),
                            "fields": {
                                "value": val
                            }
                        }]
                        client.write_points(data)

    while True:
        os.system("clear")
        for phase in reg_list:
            num_registers = reg_list[phase]["num_registers"]
            lock = Lock()
            threads = []
            for in_measure_name in reg_list[phase]:
                if in_measure_name == "num_registers":
                    continue
                th = Thread(target=operation, args=(in_measure_name, reg_list[phase][in_measure_name]))
                th.start()
                threads.append(th)
            for th in threads:
                th.join()


def learner():
    num_past_values = 120
    bcpmes = init_all_devices()
    with open(BCPME.FILE_REGISTER_MAP, "r") as file:
        config = json.load(file)
    phase = config["registers"]["1"]
    reg = phase["current"]
    if len(bcpmes) == 0:
        Terminal.log_danger("No BCPME device configured")
        exit(1)
    for bcpme in bcpmes:
        values[bcpme.name] = {1: {}, 2: {}}
        averages[bcpme.name] = {1: {}, 2: {}}
        maxs[bcpme.name] = {1: {}, 2: {}}
        mins[bcpme.name] = {1: {}, 2: {}}
    while True:
        global i
        i += 1
        for bcpme in bcpmes:
            res = bcpme.big_request_16(reg["values"], phase["num_registers"], reg["scale"])
            for unit_id in res:
                for virtual in range(1, phase["num_registers"] + 1):
                    val = res[unit_id][virtual]
                    if val != 0:
                        phys = bcpme.get_name_from_virtual(unit_id, virtual)
                        if virtual not in maxs[bcpme.name][unit_id]:
                            maxs[bcpme.name][unit_id][virtual] = val
                        if virtual not in mins[bcpme.name][unit_id]:
                            mins[bcpme.name][unit_id][virtual] = val
                        if virtual in values[bcpme.name][unit_id]:
                            values[bcpme.name][unit_id][virtual]["values"].append(val)
                        else:
                            values[bcpme.name][unit_id][virtual] = phys
                            values[bcpme.name][unit_id][virtual]["values"] = [val]
                        if val > maxs[bcpme.name][unit_id][virtual]:
                            maxs[bcpme.name][unit_id][virtual] = val
                        elif val < mins[bcpme.name][unit_id][virtual]:
                            mins[bcpme.name][unit_id][virtual] = val
                        tmp_values = values[bcpme.name][unit_id][virtual]["values"]
                        if len(tmp_values) > num_past_values:
                            tmp_values = tmp_values[len(tmp_values) - num_past_values:len(tmp_values) - 1]
                        avg = sum(tmp_values) / float(len(tmp_values))
                        averages[bcpme.name][unit_id][virtual] = avg


def checker():
    WARN_THRESHOLD = .1
    DANG_THRESHOLD = .15
    fmt = "%5s%15s%15s%10s%15s%15s"
    header = fmt % ("BCPME", "name", "actual value", "average", "all time max", "all time low")
    while True:
        if averages != {}:
            os.system('cls||clear')
            Terminal.log(
                "Total values: " + str(i) + " warning threshold: " + str(WARN_THRESHOLD) + " danger threshold: " + str(
                    DANG_THRESHOLD))
            Terminal.log(header)
            for bcpme in averages:
                for unit_id in averages[bcpme]:
                    for virtual in averages[bcpme][unit_id]:
                        avg = averages[bcpme][unit_id][virtual]
                        d = values[bcpme][unit_id][virtual]
                        value = d["values"][len(d["values"]) - 1]
                        max = maxs[bcpme][unit_id][virtual]
                        min = mins[bcpme][unit_id][virtual]
                        warning_zone = avg * WARN_THRESHOLD
                        danger_zone = avg * DANG_THRESHOLD
                        if value < avg - danger_zone or value > avg + danger_zone:
                            Terminal.log_danger(
                                fmt % (
                                    bcpme, d["name"], ("%2.2f" % value), ("%2.2f" % avg), ("%2.2f" % max),
                                    ("%2.2f" % min)))
                        elif value < avg - warning_zone or value > avg + warning_zone:
                            Terminal.log_warning(
                                fmt % (
                                    bcpme, d["name"], ("%2.2f" % value), ("%2.2f" % avg), ("%2.2f" % max),
                                    ("%2.2f" % min)))
                        else:
                            Terminal.log_nominal(
                                fmt % (
                                    bcpme, d["name"], ("%2.2f" % value), ("%2.2f" % avg), ("%2.2f" % max),
                                    ("%2.2f" % min)))

            sys.stdout.write(Terminal.RESET)
            print("", end="\r")
        time.sleep(2)


if __name__ == "__main__":
    with open(BCPME.FILE_REGISTER_MAP, "r") as file:
        config = json.load(file)
    in_reg_list = {
        1: config["registers"]["1"]
    }
    try:
        fetcher(in_reg_list)
    except KeyboardInterrupt:
        Terminal.log_danger("Closed By Keyboard, please wait closing threads...")
        exit()
