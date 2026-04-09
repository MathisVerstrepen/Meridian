FROM python:3.11-slim AS nsjail-builder

ARG NSJAIL_REF=master

RUN apt-get update && apt-get install -y --no-install-recommends \
    autoconf \
    bison \
    flex \
    g++ \
    gcc \
    git \
    libnl-route-3-dev \
    libprotobuf-dev \
    libtool \
    make \
    pkg-config \
    protobuf-compiler \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
RUN git clone --depth 1 --branch "${NSJAIL_REF}" --recurse-submodules --shallow-submodules \
    https://github.com/google/nsjail.git
WORKDIR /src/nsjail
RUN make

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV MPLBACKEND=Agg
ENV XDG_CACHE_HOME=/tmp/.cache

# Install necessary system dependencies for the Python libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    graphviz \
    libglib2.0-0 \
    libnl-route-3-200 \
    libprotobuf32 \
    libseccomp2 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=nsjail-builder /src/nsjail/nsjail /usr/local/bin/nsjail

RUN groupadd --system --gid 1000 sandboxuser && useradd --system --uid 1000 -g sandboxuser sandboxuser

# Copy requirements and install them globally
COPY ./sandbox_manager/sandbox-requirements.txt .
RUN pip install --no-cache-dir -r sandbox-requirements.txt
COPY ./sandbox_manager/worker/bootstrap.py /payload/bootstrap.py

# Pre-download NLTK data so it is available offline
RUN python -m nltk.downloader -d /usr/local/share/nltk_data punkt stopwords wordnet
RUN python -c "import matplotlib.pyplot as plt"

RUN mkdir -p /payload && chown sandboxuser:sandboxuser /payload

WORKDIR /tmp
USER sandboxuser

CMD ["python", "-c", "print('Sandbox Ready')"]
