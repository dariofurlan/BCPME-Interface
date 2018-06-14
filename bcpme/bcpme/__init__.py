import json
import os
import shutil
import socket
import struct
import sys
import time
from typing import List, Tuple


def print_header(data):
    print("\n PACKET HEADER")
    print("Transaction Id : %s" % data[0])
    print("Protocol Id : %s" % data[1])
    print("Length : %s" % data[2])
    print("Unit Id : %s" % data[3])
    print("Function Code : %s" % data[4])
    print("Byte Count : %s" % data[5])


WARNING = "\033[30;43m"
RED = "\033[97;101m"
NOMINAL = "\033[97;42m"
RESET = "\033[0;0m"


def log(message, **kwargs):
    fmts = "%-" + str(get_term_columns()) + "s"
    if kwargs.get("date", False):
        output = "%s %s" % (get_log_time(), message)
    else:
        output = "%s" % message
    print(fmts % output)


def log_danger(message, **kwargs):
    sys.stdout.write(RED)
    log(message, **kwargs)
    sys.stdout.write(RESET)


def log_warning(message, **kwargs):
    sys.stdout.write(WARNING)
    log(message, **kwargs)
    sys.stdout.write(RESET)


def log_nominal(message, **kwargs):
    sys.stdout.write(NOMINAL)
    log(message, **kwargs)
    sys.stdout.write(RESET)


def get_term_columns():
    return shutil.get_terminal_size().columns


def get_log_time():
    return time.strftime("[%Y-%m-%d %H:%M:%S]")


class BCPME:
    DEFAULT_TRANSACTION_ID = 0
    DEFAULT_PROTOCOL_ID = 0
    FILE_CONF = "bcpme.json"
    FILE_REGISTER_MAP = "bcpme_register_map.json"
    WIRE_CONFIGURATION_TYPE = ["top feed", "bottom feed", "sequential", "odd/even"]

    def __init__(self, name, **kwargs):
        self.name = name
        self.ip = kwargs.get("ip", "")
        self.wire_conf = kwargs.get("wire_conf", "")
        self.port = 502
        self.devs_in_use = {1: {}, 2: {}}
        dev_map = self.__load_from_json()
        if dev_map is None:
            dev_map = {}
        for panel_n in dev_map:
            for letter in dev_map[panel_n]:
                for physical_n in dev_map[panel_n][letter]:
                    el = dev_map[panel_n][letter][physical_n]
                    if "name" in el:
                        to_add = {"physical": int(physical_n),
                                  "panel_n": panel_n,
                                  "panel_letter": letter,
                                  "name": el["name"]}
                        if "phase" in el:
                            to_add["phase"] = el["phase"]
                        else:
                            to_add["phase"] = 0
                        # print("imported from json: ", to_add["name"])
                        self.devs_in_use[int(panel_n)][el["virtual"]] = to_add
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.ip, self.port))
        for n in range(4):
            if self.wire_conf == BCPME.WIRE_CONFIGURATION_TYPE[n]:
                self.change_configuration(n)
                break

    def __request_read(self, start_register, num_registers, unit_id):
        length = 2 + 4
        function_code = 4
        request = struct.pack(">3H 2B 2H", BCPME.DEFAULT_TRANSACTION_ID, BCPME.DEFAULT_PROTOCOL_ID, length, unit_id,
                              function_code, int(start_register) - 1, int(num_registers))
        self.sock.send(request)

    def request_edit_single(self, reg_n, unit_id, value):
        """
        Write a value inside a register of the unit id
        :param reg_n: the register number to edit
        :param unit_id: the unit id
        :param value: the value to write into the register
        """
        length = 6
        function_code = 6
        request = struct.pack(">3H 2B 1H 1h", BCPME.DEFAULT_TRANSACTION_ID, BCPME.DEFAULT_PROTOCOL_ID, length,
                              unit_id, function_code,
                              int(reg_n) - 1, int(value))
        self.sock.send(request)
        st = struct.Struct(">3H 2B 1H 1h")
        response = self.sock.recv(st.size)
        print(st.unpack(response))

    def request_single_int_16(self, register_n, unit_id, scale_reg_n=0):
        """
        Read the 16 bit signed register with the relative scale_reg register if given of the unit id
        :param register_n: the number of the register to read
        :param unit_id: the unit id
        :param scale_reg_n: the register used as a scale_reg
        :return: the value stored
        """
        st = struct.Struct(">3H 3B 1h")
        self.__request_read(register_n, 1, unit_id)
        response = self.sock.recv(st.size)
        # print("binary: %s%s" % (format(response[len(response)-2], "08b"), format(response[len(response)-1], "08b")))
        data = st.unpack(response)
        scale = self.request_single_int_16(scale_reg_n, unit_id) if (scale_reg_n != 0) else 0
        # print(data[6])

        return data[6] * pow(10, scale)

    def request_single_int_32(self, register_n, unit_id, scale_reg_n=0):
        """
        Read the 32 bit signed register with the relative scale_reg register if given of the unit id
        :param register_n: the number of the register to read
        :param unit_id: the unit id
        :param scale_reg_n: the register used as a scale_reg
        :return: the value requested
        """
        st = struct.Struct(">3H 3B 1l")  # find out if is signed or not signed "l" is signed , "L" unsigned
        self.__request_read(register_n, 2, unit_id)

        response = self.sock.recv(st.size)
        data = st.unpack(response)
        scale = self.request_single_int_16(scale_reg_n, unit_id) if (scale_reg_n != 0) else 0
        return data[6] * pow(10, scale)

    def request_single_float_32(self, register_n, unit_id):
        """
        Read the 32 bit float value of the unit id
        :param register_n: the number of the register to read of the unit id
        :param unit_id: the unit id
        :return: the value requested
        """
        st = struct.Struct(">3H 3B 1f")
        self.__request_read(register_n, 2, unit_id)
        response = self.sock.recv(st.size)
        data = st.unpack(response)
        return data[6]

    def big_request_16(self, register_n: int, num_registers: int, scale_reg_n: int) -> dict:
        """
        Use this to request all measures about this device only for 16 bit measures
        :param register_n: the first value register number
        :param num_registers: the number of registers
        :param scale_reg_n: the first scale register number
        :return: a dict containing all the 16 bit values properly scaled
        """
        st = struct.Struct(">3H 3B %sh" % num_registers)
        values = {1: [], 2: []}
        scales = {1: [], 2: []}

        self.__request_read(register_n, num_registers, 1)
        resp = st.unpack(self.sock.recv(st.size))
        values[1] = resp[6:len(resp)]

        self.__request_read(register_n, num_registers, 2)
        resp = st.unpack(self.sock.recv(st.size))
        values[2] = resp[6:len(resp)]

        if scale_reg_n <= 0:
            scales[1] = [scale_reg_n for x in range(num_registers)]
            scales[2] = [scale_reg_n for x in range(num_registers)]
        else:
            self.__request_read(scale_reg_n, num_registers, 1)
            resp = st.unpack(self.sock.recv(st.size))
            scales[1] = resp[6:len(resp)]

            self.__request_read(scale_reg_n, num_registers, 2)
            resp = st.unpack(self.sock.recv(st.size))
            scales[2] = resp[6:len(resp)]

        result = {1: {}, 2: {}}
        for x in range(1, num_registers + 1):
            result[1][x] = {}
            result[2][x] = {}

        for unit_id in range(1, 3):
            for i in range(1, num_registers + 1):
                result[unit_id][i] = values[unit_id][i - 1] * pow(10, scales[unit_id][i - 1])
        return result

    def big_request_32(self, register_n, num_registers, scale_reg_n):
        """
        Use this to request all measures about this device only for 32 bit measures
        :param register_n: the first value register number
        :param num_registers: the number of registers
        :param scale_reg_n: the first scale register number
        :return: a dict containing all the 32 bit values properly scaled
        """
        st = struct.Struct(">3H 3B %sl" % num_registers)
        values = {1: [], 2: []}
        scales = {1: [], 2: []}

        self.__request_read(register_n, num_registers * 2, 1)
        resp = st.unpack(self.sock.recv(st.size))
        values[1] = resp[6:len(resp)]

        self.__request_read(register_n, num_registers * 2, 2)
        resp = st.unpack(self.sock.recv(st.size))
        values[2] = resp[6:len(resp)]

        self.__request_read(scale_reg_n, num_registers * 2, 1)
        resp = st.unpack(self.sock.recv(st.size))
        scales[1] = resp[6:len(resp)]

        self.__request_read(scale_reg_n, num_registers * 2, 2)
        resp = st.unpack(self.sock.recv(st.size))
        scales[2] = resp[6:len(resp)]

        result = {1: {}, 2: {}}
        for x in range(1, num_registers + 1):
            result[1][x] = {}
            result[2][x] = {}

        for unit_id in range(1, 3):
            for i in range(1, num_registers + 1):
                result[unit_id][i] = values[unit_id][i - 1] * pow(10, scales[unit_id][i - 1])
        return result

    def get_name_from_virtual(self, unit_id, virtual):
        if virtual not in self.devs_in_use[unit_id]:
            self.new_dev_from_virtual(unit_id, virtual, "")
        return self.devs_in_use[unit_id][virtual]

    def change_configuration(self, num_of_configuration):
        self.request_edit_single(6, 1, num_of_configuration)
        self.request_edit_single(6, 2, num_of_configuration)

    def set_user_defined_status(self, unit_id, status: bool):
        out = 1 if status else 0
        self.request_edit_single(62017, unit_id, out)

    def set_phase(self, unit_id, virtual, phase):
        start = 62115
        self.request_edit_single(start + virtual, unit_id, phase)

    def new_dev_from_virtual(self, unit_id, virtual, name, phase=0):
        """
        Add a new device using references from the register side
        :param unit_id: the unit id
        :param virtual: the virtual number
        :param name: the name of the device
        :param phase: the phase of the device
        """
        letter, number = self.virtual_to_physical(virtual)
        to_add = {"physical": number,
                  "panel_n": unit_id,
                  "panel_letter": letter,
                  "name": name,
                  "phase": phase}
        self.devs_in_use[unit_id][virtual] = to_add
        self.__save_dev_state()

    def new_dev_from_physical(self, panel_n: int, panel_letter: str, physical: int, name: str, phase: int = 0):
        """
        Add a new device using references from the physical side
        :param panel_n: the panel number
        :param panel_letter: the panel letter
        :param physical: the number physically written on the panel
        :param name: the name of the device
        :param phase: the phase of the device
        """
        panel_letter = panel_letter.capitalize()
        to_add = {
            "physical": physical,
            "panel_n": panel_n,
            "panel_letter": panel_letter,
            "name": name,
            "phase": phase
        }
        virtual = self.physical_to_virtual(panel_letter, physical)
        self.set_phase(panel_n, virtual, phase)
        self.devs_in_use[panel_n][virtual] = to_add
        self.__save_dev_state()

    def virtual_to_physical(self, virtual) -> Tuple[str, int]:
        """
        Convert a virtual reference to a physical reference returning a tuple of: panel_letter, physical_number
        :param virtual: the virtual number
        :return: the corresponding panel letter and physical number in a Tuple[ panel_letter, physical_number]
        """
        if self.wire_conf == BCPME.WIRE_CONFIGURATION_TYPE[0]:
            if virtual % 2 == 0:
                return "B", int(virtual / 2)
            else:
                return "A", int(virtual / 2) + 1
        if self.wire_conf == BCPME.WIRE_CONFIGURATION_TYPE[1]:
            if virtual % 2 == 0:
                return "A", int((44 - virtual) / 2)
            else:
                return "B", int((43 - virtual) / 2)
        if self.wire_conf == BCPME.WIRE_CONFIGURATION_TYPE[2]:
            if virtual <= 21:
                return "A", 22 - virtual
            else:
                return "B", virtual - 21
        if self.wire_conf == BCPME.WIRE_CONFIGURATION_TYPE[3]:
            if virtual % 2 == 0:
                return "B", int(virtual / 2)
            else:
                return "A", int((43 - virtual) / 2)

    def physical_to_virtual(self, panel_letter: str, physical_number: int):
        """
        Convert a physical reference to a virtual reference returning the virtual number
        :param panel_letter: the panel letter
        :param physical_number: the number physically written on the panel
        :return: the corresponding virtual number
        """
        panel_letter = panel_letter.capitalize()
        if self.wire_conf == BCPME.WIRE_CONFIGURATION_TYPE[0]:
            if panel_letter == "A":
                return 2 * physical_number - 1
            elif panel_letter == "B":
                return 2 * physical_number
        elif self.wire_conf == BCPME.WIRE_CONFIGURATION_TYPE[1]:
            if panel_letter == "A":
                return 43 - (2 * physical_number - 1)
            elif panel_letter == "B":
                return 43 - (2 * physical_number)
        elif self.wire_conf == BCPME.WIRE_CONFIGURATION_TYPE[2]:
            if panel_letter == "A":
                return 22 - physical_number
            elif panel_letter == "B":
                return 21 + physical_number
        elif self.wire_conf == BCPME.WIRE_CONFIGURATION_TYPE[3]:
            if panel_letter == "A":
                return 43 - (2 * physical_number)
            elif panel_letter == "B":
                return 2 * physical_number

    def __save_dev_state(self):
        dev_map = {'1': {'A': {}, 'B': {}}, '2': {'A': {}, 'B': {}}}
        if self.wire_conf == BCPME.WIRE_CONFIGURATION_TYPE[0]:
            # top feed
            odd = [x for x in range(1, 43, 2)]
            even = [x for x in range(2, 43, 2)]
            for n in range(21):
                dev_map["1"]["A"][n + 1] = {"virtual": odd[n]}
                dev_map["2"]["A"][n + 1] = {"virtual": odd[n]}
                dev_map["1"]["B"][n + 1] = {"virtual": even[n]}
                dev_map["2"]["B"][n + 1] = {"virtual": even[n]}
        elif self.wire_conf == BCPME.WIRE_CONFIGURATION_TYPE[1]:
            # bottom feed
            reverse_odd = [x for x in range(41, 0, -2)]
            reverse_even = [x for x in range(42, 0, -2)]
            for n in range(21):
                dev_map["1"]["A"][n + 1] = {"virtual": reverse_even[n]}
                dev_map["2"]["A"][n + 1] = {"virtual": reverse_even[n]}
                dev_map["1"]["B"][n + 1] = {"virtual": reverse_odd[n]}
                dev_map["2"]["B"][n + 1] = {"virtual": reverse_odd[n]}
        elif self.wire_conf == BCPME.WIRE_CONFIGURATION_TYPE[2]:
            # sequential
            seq_1 = [x for x in range(21, 0, -1)]
            seq_2 = [x for x in range(22, 43)]
            for n in range(21):
                dev_map["1"]["A"][n + 1] = {"virtual": seq_1[n]}
                dev_map["2"]["A"][n + 1] = {"virtual": seq_1[n]}
                dev_map["1"]["B"][n + 1] = {"virtual": seq_2[n]}
                dev_map["2"]["B"][n + 1] = {"virtual": seq_2[n]}
        elif self.wire_conf == BCPME.WIRE_CONFIGURATION_TYPE[3]:
            # odd/even
            reverse_odd = [x for x in range(41, 0, -2)]
            even = [x for x in range(2, 43, 2)]
            for n in range(21):
                dev_map["1"]["A"][n + 1] = {"virtual": reverse_odd[n]}
                dev_map["2"]["A"][n + 1] = {"virtual": reverse_odd[n]}
                dev_map["1"]["B"][n + 1] = {"virtual": even[n]}
                dev_map["2"]["B"][n + 1] = {"virtual": even[n]}

        for dev_val in self.devs_in_use[1].values():
            dev_map[str(dev_val["panel_n"])][dev_val["panel_letter"]][dev_val["physical"]]["name"] = dev_val["name"]
        for dev_val in self.devs_in_use[2].values():
            dev_map[str(dev_val["panel_n"])][dev_val["panel_letter"]][dev_val["physical"]]["name"] = dev_val["name"]
        if not os.path.exists(BCPME.FILE_CONF):
            with open(BCPME.FILE_CONF, "w+") as file:
                file.write("{}")
        with open(BCPME.FILE_CONF, "r") as file_r:
            s = file_r.read()
            if s == "":
                s = "{}"
            with open(BCPME.FILE_CONF, "w") as file_w:
                tmp = json.loads(s)
                tmp[self.name] = {"ip": self.ip, "dev_map": dev_map, "wire_conf": self.wire_conf}
                json.dump(tmp, file_w)

    def __load_from_json(self):
        if not os.path.exists(BCPME.FILE_CONF):
            with open(BCPME.FILE_CONF, "w+") as file:
                file.write("{}")
        else:
            with open(BCPME.FILE_CONF, "r") as file_r:
                s = file_r.read()
                s = "{}" if s == "" else s
                j = json.loads(s)
                if len(j) != 0:
                    if self.name in j:
                        self.ip = j[self.name]["ip"] if self.ip == "" else self.ip
                        self.wire_conf = j[self.name]["wire_conf"] if self.wire_conf == "" else self.wire_conf
                        return j[self.name]["dev_map"]
                return None

    def __str__(self) -> str:
        return "Name: %s,  IP: %s,  Wire Configuration: %s" % (self.name, self.ip, self.wire_conf)


def init_all_devices() -> List[BCPME]:
    """
    Initialize all devices already stored in the json file
    :return: list of BCPME objects from the json file
    """
    if not os.path.exists(BCPME.FILE_CONF):
        with open(BCPME.FILE_CONF, "w+") as file:
            file.write("{}")
        return []
    else:
        with open(BCPME.FILE_CONF, "r") as file_r:
            s = file_r.read()
            s = "{}" if s == "" else s
            j = json.loads(s)
            objs = []
            for key, val in j.items():
                objs.append(BCPME(ip=val["ip"], name=key, wire_conf=val["wire_conf"]))
            return objs
