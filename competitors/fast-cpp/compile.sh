#!/usr/bin/env bash

c++ -O3 -std=c++20 fast-wc.cpp utils.cpp -lpthread -lstdc++fs -o fast-wc
