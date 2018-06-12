#! /usr/bin/python3.5
import json
import os
import sys
import time
from threading import Thread

from util import BCPME, Terminal

values = {}
averages = {}
i = 0


def learner():
    num_past_values = 120
    bcpmes = BCPME.init_all_devices()
    with open(BCPME.FILE_REGISTER_MAP, "r") as file:
        config = json.load(file)
    phase = config["registers"]["1"]
    reg = phase["current"]
    if len(bcpmes) == 0:
        Terminal.log_danger("No BCPME device configured")
        exit(0)
    for bcpme in bcpmes:
        values[bcpme.name] = {1: {}, 2: {}}
        averages[bcpme.name] = {1: {}, 2: {}}
    while True:
        global i
        i += 1
        for bcpme in bcpmes:
            res = bcpme.big_request(reg["values"], phase["num_registers"], reg["scale"])
            for n in res:
                for meter in range(1, phase["num_registers"] + 1):
                    val = res[n][meter]
                    if val != 0:
                        phys = bcpme.get_name_from_virtual(n, meter)

                        if meter in values[bcpme.name][n]:
                            values[bcpme.name][n][meter]["values"].append(val)
                        else:
                            values[bcpme.name][n][meter] = phys
                            values[bcpme.name][n][meter]["values"] = [val]

                        tmp_values = values[bcpme.name][n][meter]["values"]
                        if len(tmp_values) > num_past_values:
                            tmp_values = tmp_values[len(tmp_values) - num_past_values:len(tmp_values) - 1]
                        avg = sum(tmp_values) / float(len(tmp_values))
                        averages[bcpme.name][n][meter] = avg


def checker():
    WARN_THRESHOLD = .1
    DANG_THRESHOLD = .15
    fmt = "%11s  mean:%2.2f  %2.2f  >  %2.2f  >  %2.2f"
    while True:
        if averages != {}:
            os.system('cls||clear')
            print("number: %s" % i)
            for bcpme in averages:
                for unit_id in averages[bcpme]:
                    for virtual in averages[bcpme][unit_id]:
                        avg = averages[bcpme][unit_id][virtual]
                        d = values[bcpme][unit_id][virtual]
                        value = d["values"][len(d["values"]) - 1]
                        warning_zone = avg * WARN_THRESHOLD
                        danger_zone = avg * DANG_THRESHOLD
                        if value < avg - danger_zone or value > avg + danger_zone:
                            Terminal.log_danger(fmt % (d["name"], avg, avg - danger_zone, value, avg + danger_zone))
                        elif value < avg - warning_zone or value > avg + warning_zone:
                            Terminal.log_warning(fmt % (d["name"], avg, avg - warning_zone, value, avg + warning_zone))
                        else:
                            Terminal.log_nominal(fmt % (d["name"], avg, avg - warning_zone, value, avg + warning_zone))

            sys.stdout.write(Terminal.RESET)
            print("", end="\r")
        time.sleep(2)


if __name__ == "__main__":
    i = 0
    Thread(target=learner, daemon=True).start()
    Thread(target=checker, daemon=True).start()
    while True:
        pass
