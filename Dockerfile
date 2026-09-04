ARG SYSBASE=quay.io/almalinuxorg/10-base
FROM ${SYSBASE} AS system-build

LABEL maintainer="appthreat" \
      org.opencontainers.image.authors="Team AppThreat <cloud@appthreat.com>" \
      org.opencontainers.image.source="https://github.com/appthreat/atom-tools" \
      org.opencontainers.image.url="https://github.com/appthreat/atom-tools" \
      org.opencontainers.image.version="0.9.x" \
      org.opencontainers.image.vendor="AppThreat" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.title="atom-tools" \
      org.opencontainers.image.description="Collection of tools for use with AppThreat/atom, including Android apk analysis." \
      org.opencontainers.docker.cmd="docker run --rm -it -v /tmp:/tmp -v $(pwd):/app:rw -w /app -t ghcr.io/appthreat/atom-tools"

RUN mkdir -p /mnt/sys-root; \
    dnf install --installroot /mnt/sys-root glibc-minimal-langpack microdnf java-21-openjdk-headless findutils which tar gzip zip unzip sudo nodejs nodejs-devel \
    bzip2 python3 python3-devel python3-pip \
    --releasever 10 --setopt install_weak_deps=false --nodocs -y; \
    dnf --installroot /mnt/sys-root clean all;
RUN rm -rf /mnt/sys-root/var/cache/dnf /mnt/sys-root/var/log/dnf* /mnt/sys-root/var/lib/dnf /mnt/sys-root/var/log/yum.*; \
    /bin/date +%Y%m%d_%H%M > /mnt/sys-root/etc/BUILDTIME ;  \
    echo '%_install_langs C.utf8' > /mnt/sys-root/etc/rpm/macros.image-language-conf; \
    echo 'LANG="C.utf8"' >  /mnt/sys-root/etc/locale.conf; \
    echo 'container' > /mnt/sys-root/etc/dnf/vars/infra; \
    rm -f /mnt/sys-root/etc/machine-id; \
    touch /mnt/sys-root/etc/machine-id; \
    touch /mnt/sys-root/etc/resolv.conf; \
    touch /mnt/sys-root/etc/hostname; \
    touch /mnt/sys-root/etc/.pwd.lock; \
    chmod 600 /mnt/sys-root/etc/.pwd.lock; \
    rm -rf /mnt/sys-root/usr/share/locale/en* /mnt/sys-root/boot /mnt/sys-root/dev/null /mnt/sys-root/var/log/hawkey.log ; \
    echo '0.0 0 0.0' > /mnt/sys-root/etc/adjtime; \
    echo '0' >> /mnt/sys-root/etc/adjtime; \
    echo 'UTC' >> /mnt/sys-root/etc/adjtime; \
    mkdir -p /mnt/sys-root/run/lock; \
    cd /mnt/sys-root/etc ; \
    ln -s ../usr/share/zoneinfo/UTC localtime

FROM scratch

COPY --link --from=system-build /mnt/sys-root/ /

ENV ANDROID_HOME=/opt/android-sdk-linux \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING="utf-8" \
    NYXSTONE_LLVM_PREFIX="/usr/lib64/llvm18"
ENV PATH=${PATH}:/usr/local/bin/:/root/.local/bin:${ANDROID_HOME}/cmdline-tools/latest/bin:${ANDROID_HOME}/tools:${ANDROID_HOME}/tools/bin:${ANDROID_HOME}/platform-tools:

RUN microdnf install -y make gcc g++ ncurses nodejs nodejs-devel npm \
    && alternatives --install /usr/bin/python3 python /usr/bin/python3.12 1 \
    && python3 --version \
    && python3 -m pip install --upgrade pip \
    && python3 -m pip install setuptools --upgrade \
    && microdnf install -y epel-release \
    && microdnf install -y --enablerepo=epel llvm18 llvm18-devel \
    && mkdir -p ${ANDROID_HOME}/cmdline-tools \
    && curl -L https://dl.google.com/android/repository/commandlinetools-linux-13114758_latest.zip -o ${ANDROID_HOME}/cmdline-tools/android_tools.zip \
    && unzip ${ANDROID_HOME}/cmdline-tools/android_tools.zip -d ${ANDROID_HOME}/cmdline-tools/ \
    && rm ${ANDROID_HOME}/cmdline-tools/android_tools.zip \
    && mv ${ANDROID_HOME}/cmdline-tools/cmdline-tools ${ANDROID_HOME}/cmdline-tools/latest \
    && yes | /opt/android-sdk-linux/cmdline-tools/latest/bin/sdkmanager --licenses --sdk_root=/opt/android-sdk-linux \
    && /opt/android-sdk-linux/cmdline-tools/latest/bin/sdkmanager 'platform-tools' --sdk_root=/opt/android-sdk-linux \
    && /opt/android-sdk-linux/cmdline-tools/latest/bin/sdkmanager 'platforms;android-36' --sdk_root=/opt/android-sdk-linux \
    && /opt/android-sdk-linux/cmdline-tools/latest/bin/sdkmanager 'build-tools;36.0.0' --sdk_root=/opt/android-sdk-linux

COPY . /opt/atom-tools
RUN npm install -g @appthreat/atom @cyclonedx/cdxgen --omit=dev \
    && atom --help \
    && python3 -m pip install --no-cache-dir "blint[extended]" \
    && blint --help \
    && python3 -m pip install --no-cache-dir /opt/atom-tools \
    && chmod a-w -R /opt \
    && npm cache clean --force \
    && microdnf clean all \
    && rm -rf /root/.npm /root/.cache /tmp/* /var/cache/dnf /var/tmp/*

# Analyzer binaries that produce the reports consumed by the convert command.
# rusi analyses Rust projects and golem analyses Go projects. They are published
# per platform in the cdxgen-plugins-bin GitHub releases together with a .sha256
# sidecar, which is downloaded and verified before the binary is installed.
# Bump CDXGEN_PLUGINS_BIN_VERSION to move to a newer release.
ARG CDXGEN_PLUGINS_BIN_VERSION=3.1.0
ARG TARGETARCH
RUN set -eux; \
    arch="${TARGETARCH:-$(uname -m)}"; \
    case "${arch}" in \
        x86_64|amd64) arch="amd64" ;; \
        aarch64|arm64) arch="arm64" ;; \
        armv7l|armv6l|arm) arch="arm" ;; \
        ppc64le) arch="ppc64le" ;; \
        riscv64) arch="riscv64" ;; \
        *) echo >&2 "unsupported architecture for analyzer binaries: ${arch}"; exit 1 ;; \
    esac; \
    workdir="$(mktemp -d)"; \
    cd "${workdir}"; \
    base_url="https://github.com/cdxgen/cdxgen-plugins-bin/releases/download/v${CDXGEN_PLUGINS_BIN_VERSION}"; \
    for tool in rusi golem; do \
        asset="${tool}-linux-${arch}"; \
        curl -fsSL --retry 3 -o "${asset}" "${base_url}/${asset}"; \
        curl -fsSL --retry 3 -o "${asset}.sha256" "${base_url}/${asset}.sha256"; \
        expected="$(cut -d " " -f1 "${asset}.sha256")"; \
        actual="$(sha256sum "${asset}" | cut -d " " -f1)"; \
        echo "${asset}: expected ${expected} got ${actual}"; \
        if [ "${expected}" != "${actual}" ]; then \
            echo >&2 "sha256 mismatch for ${asset}"; exit 1; \
        fi; \
        install -m 0755 "${asset}" "/usr/local/bin/${tool}"; \
        "/usr/local/bin/${tool}" --help > /dev/null; \
    done; \
    cd /; \
    rm -rf "${workdir}"

ENTRYPOINT [ "atom-tools" ]
