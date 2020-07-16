FROM ubuntu:18.04

# Install Python and Boost.
RUN \
  apt-get update \
  && apt-get install -y python-pip python3-pip python3-dev libboost-all-dev git nano vim gdb \
  && apt-get install -y build-essential cppcheck clang-tidy clang g++ g++-multilib gcc gcc-multilib \
  && pip3 install tox black numpy

# Define working directory.
WORKDIR /data

ENV IBISAMI_ROOT=/data/PyAMI/ibisami
ENV BOOST_ROOT=/usr/include/boost
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

# Define default command.
CMD ["bash"]
