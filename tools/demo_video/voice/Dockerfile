# The narrator for the demo video: Kokoro-82M, an open-source neural text-to-speech model
# (Apache-2.0, https://huggingface.co/hexgrad/Kokoro-82M), run locally. The image downloads the
# package and the model once, at build time; speaking then runs with no network at all.
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends espeak-ng libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# CPU-only PyTorch first, so pip does not pull a larger build
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir "kokoro>=0.9.4" soundfile

# Bake the model, the voices and the English text front end into the image.
ARG VOICES="af_heart am_michael bm_george"
RUN python -c "import sys; from kokoro import KPipeline; \
[list(KPipeline(lang_code=v[0])('Warm up.', voice=v)) for v in sys.argv[1].split()]" "$VOICES"

ENV HF_HUB_OFFLINE=1 PYTHONUNBUFFERED=1
WORKDIR /work
COPY speak.py /opt/speak.py
ENTRYPOINT ["python", "/opt/speak.py"]
