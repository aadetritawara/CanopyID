FROM public.ecr.aws/lambda/python:3.12

# Install libsndfile (needed by librosa) and extraction tools
RUN dnf install -y libsndfile tar xz gzip

# Download and install a static build of FFmpeg
RUN curl -O https://johnvansickle.com/ffmpeg/builds/ffmpeg-git-amd64-static.tar.xz \
    && tar xvf ffmpeg-git-amd64-static.tar.xz \
    && mv ffmpeg-git-*-static/ffmpeg /usr/local/bin/ \
    && mv ffmpeg-git-*-static/ffprobe /usr/local/bin/ \
    && rm -rf ffmpeg-*

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the BirdNET model to ensure classification can run without needing internet access
RUN python -c "import sys; import ai_edge_litert; sys.modules['tflite_runtime'] = ai_edge_litert; from birdnetlib.analyzer import Analyzer; Analyzer()"

# Copy the Lambda function code
COPY lambda_handler.py .

CMD [ "lambda_handler.lambda_handler" ]
