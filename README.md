# BCPME284S

This a little guide with all the things to know to communicate correctly with the Modbus device BCPME284S by Schneider Electric

### Table of Contents

* [Docs](#docs:)
* [Modbus TCP/IP](#modbus-tcp/ip)
* [Unit Id](#unit-id)
* [Function Code](#function-code)
* [Authors](#authors)

#### Docs:

* [User Guide](./doc/BCPME_user%20guide.pdf) - User Guide for the installation of BCPME
* [Register List](./doc/BCPMSC_Register_List.pdf) - Register List
* [Simply Modbus](http://www.simplymodbus.ca/TCP.htm) - Simple guide with examples to learn about the modbus TCP/IP protocol
* [Modbus Wikipedia](https://en.wikipedia.org/wiki/Modbus) - Wikipedia page about modbus and all different types (useful for function code)

## Modbus TCP/IP

This device communicate with the Modbus protocol over TCP/IP
the modbus request, as you can see int the docs, is built in this precise order:

* **2 bytes** transaction id (`0` in our case)
* **2 bytes** protocol id (`0` in our case)
* **2 bytes** length: the following number of bytes (usually `6` in our case)
* **1 bytes** [unit id](#unit-id): see the section about unit id (`1` or `2` in our case)
* **1 bytes** [function code](#function-code): the function code that tells the action to do (`4` to read, `6` to write)
* **x bytes** data: depends on the function code

### Unit Id

The Modbus device is composed of 4 panels and each one has a number and a letter assigned, we have:

* Panel 1A
* Panel 1B
* Panel 2A
* Panel 2B

each panel has 21 sensors each one numbered physically from 1 to 21, 
but seen from the software perspective **Panel 1A** and  **Panel 1B** ( the same for **Panel 2A** and **Panel 2B**) are just one block that goes from 1 to 42:

* to access Panel 1 (A and B) we use `1` for the "unit id" byte in the modbus request
* to access Panel 2 (A and B) we use `2` for the "unit id" byte in the modbus request

but the number that are written on the panels and the number of registers doesn't always match this is because as you can se at [Page 15 of The User Guide](./doc/BCPME_user%20guide.pdf)
there are 4 types of configuration.

the following table match the physical number with the "virtual" one:

![Alt text](doc/physical_virtual.svg)

To set the type of the configuration you have to write to the register number `6` the corresponding value of the configuration:

* `0` - Top Feed
* `1` - Bottom Feed
* `2` - Sequential
* `3` - Odd / Even

### Function Code

There are around 20 different type of operations supported, we are just intrested in 2

* Read Input Register: (function code:`4`) to read one or more register and the "data" bytes are used as following
    * **2 bytes** number of the first register to read
    * **2 bytes** number of registers to read
* Write Single Holding Register: (function code:`6`) to write one register the "data" bytes are used as following
    * **2 bytes** number of the register to write
    * **2 bytes** the value to write

> little note:
The numbers of the registers in the documentations of the bcpme are augmented by 1 it means that for ex.
to access the register described as number 6 in the docs, we have to use number 5

### Multi Phase

In order to access the registers that contains data about multi phase measures you have to enable "user defined status register" number `62017` with `1` 
and if needed assign to the registers starting from `62116` to `62157` and write the val `0` for phase 1,`1` for phase 2,`2` for phase 3 

## Authors

* **Dario Furlan** - *Initial work* - [https://github.com/iofurlan](https://github.com/iofurlan)

## License

This project is licensed under the MIT License - see the [LICENSE.md](./doc/LICENSE.md) file for details

