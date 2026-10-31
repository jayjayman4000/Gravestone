# Preparation is online; the acceptance container runs offline with no caps.
FROM debian:bookworm
RUN apt-get update -qq \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       qemu-system-x86 ovmf xorriso e2fsprogs python3 fdisk mtools dosfstools \
    && rm -rf /var/lib/apt/lists/*
CMD ["sleep", "infinity"]
