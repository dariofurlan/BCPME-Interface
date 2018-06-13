#! /usr/bin/python3.5
import json
import os
import sys
import time
from threading import Thread

from util import BCPME, Terminal

values = {}
averages = {}
maxs = {}
mins = {}
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
        maxs[bcpme.name] = {1: {}, 2: {}}
        mins[bcpme.name] = {1: {}, 2: {}}
    while True:
        global i
        i += 1
        for bcpme in bcpmes:
            res = bcpme.big_request_16(reg["values"], phase["num_registers"], reg["scale"])
            for n in res:
                for meter in range(1, phase["num_registers"] + 1):
                    val = res[n][meter]
                    if val != 0:
                        phys = bcpme.get_name_from_virtual(n, meter)
                        if meter not in maxs[bcpme.name][n]:
                            maxs[bcpme.name][n][meter] = val
                        if meter not in mins[bcpme.name][n]:
                            mins[bcpme.name][n][meter] = val
                        if meter in values[bcpme.name][n]:
                            values[bcpme.name][n][meter]["values"].append(val)
                        else:
                            values[bcpme.name][n][meter] = phys
                            values[bcpme.name][n][meter]["values"] = [val]
                        if val > maxs[bcpme.name][n][meter]:
                            maxs[bcpme.name][n][meter] = val
                        elif val < mins[bcpme.name][n][meter]:
                            mins[bcpme.name][n][meter] = val
                        tmp_values = values[bcpme.name][n][meter]["values"]
                        if len(tmp_values) > num_past_values:
                            tmp_values = tmp_values[len(tmp_values) - num_past_values:len(tmp_values) - 1]
                        avg = sum(tmp_values) / float(len(tmp_values))
                        averages[bcpme.name][n][meter] = avg


def checker():
    WARN_THRESHOLD = .1
    DANG_THRESHOLD = .15
    fmt = "%5s%15s%15s%10s%15s%15s"
    header = fmt % ("BCPME", "name", "actual value", "average", "all time max", "all time low")
    while True:
        if averages != {}:
            os.system('cls||clear')
            Terminal.log("Total values: " + str(i))
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
                                fmt % (bcpme, d["name"], ("%2.2f" % value), ("%2.2f" % avg), ("%2.2f" % max), ("%2.2f" % min)))
                        elif value < avg - warning_zone or value > avg + warning_zone:
                            Terminal.log_warning(
                                fmt % (bcpme, d["name"], ("%2.2f" % value), ("%2.2f" % avg), ("%2.2f" % max), ("%2.2f" % min)))
                        else:
                            Terminal.log_nominal(
                                fmt % (bcpme, d["name"], ("%2.2f" % value), ("%2.2f" % avg), ("%2.2f" % max), ("%2.2f" % min)))

            sys.stdout.write(Terminal.RESET)
            print("", end="\r")
        time.sleep(2)


def checker2():
    def log_checker_line(color1, name1, val1, color2, name2, val2):
        columns = Terminal.get_term_columns()
        out1 = "%s: %2.2f" % (name1, val1)
        out2 = "%s: %2.2f" % (name2, val1)
        space1_sx = ("%" + str(int(columns / 4) - len(out1) / 2) + "s") % ""
        space1_dx = ("%" + str(int(columns / 4) - len(out1) / 2) + "s") % ""
        space2_sx = ("%" + str(int(columns / 4) - len(out2) / 2) + "s") % ""
        space2_dx = ("%" + str(int(columns / 4) - len(out2) / 2) + "s") % ""
        return "%s%s%s%s%s%s%s%s%s%s\n" % (
            space1_sx, color1, out1, Terminal.RESET, space1_dx, space2_sx, color2, out2, Terminal.RESET, space2_dx)

    WARN_THRESHOLD = .1
    DANG_THRESHOLD = .15
    while True:
        if averages != {}:
            for bcpme in averages:
                os.system('cls||clear')
                print("number: %s" % i)
                bcpme = "A"
                out = ""
                for virtual in range(1, 43):
                    name1 = str(virtual) + " - "
                    name2 = str(virtual) + " - "
                    value1 = 0.0
                    value2 = 0.0
                    color1 = ""
                    color2 = ""
                    if virtual in averages[bcpme][1]:
                        name1 += values[bcpme][1][virtual]["name"]
                        value1 = values[bcpme][1][virtual]["values"][len(values[bcpme][1][virtual]["values"]) - 1]
                        avg = averages[bcpme][1][virtual]
                        warning_zone = avg * WARN_THRESHOLD
                        danger_zone = avg * DANG_THRESHOLD
                        if value1 < avg - danger_zone or value1 > avg + danger_zone:
                            color1 = Terminal.RED
                        elif value1 < avg - warning_zone or value1 > avg + warning_zone:
                            color1 = Terminal.WARNING
                        else:
                            color1 = Terminal.NOMINAL
                    if virtual in averages[bcpme][2]:
                        name2 += values[bcpme][2][virtual]["name"]
                        value2 = values[bcpme][2][virtual]["values"][len(values[bcpme][2][virtual]["values"]) - 1]
                        avg = averages[bcpme][2][virtual]
                        warning_zone = avg * WARN_THRESHOLD
                        danger_zone = avg * DANG_THRESHOLD
                        if value2 < avg - danger_zone or value2 > avg + danger_zone:
                            color2 = Terminal.RED
                        elif value2 < avg - warning_zone or value2 > avg + warning_zone:
                            color2 = Terminal.WARNING
                        else:
                            color2 = Terminal.NOMINAL
                    out += log_checker_line(color1, name1, value1, color2, name2, value2)
                sys.stdout.write(out)
                sys.stdout.write(Terminal.RESET)
                print("", end="\r")
        time.sleep(2)


if __name__ == "__main__":
    i = 0
    Thread(target=learner, daemon=True).start()
    Thread(target=checker, daemon=True).start()
    try:
        while True:
            pass
    except KeyboardInterrupt:
        print("Closed By Keyboard")
        exit()
