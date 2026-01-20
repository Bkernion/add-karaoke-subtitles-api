FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    wget \
    fonts-liberation \
    fonts-dejavu-core \
    fonts-dejavu-extra \
    fonts-noto-core \
    fonts-opensymbol \
    fonts-freefont-ttf \
    fontconfig \
    && fc-cache -f -v \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Register bundled fonts with fontconfig
RUN mkdir -p /etc/fonts/conf.d && \
    echo '<?xml version="1.0"?>' > /etc/fonts/conf.d/99-custom-fonts.conf && \
    echo '<!DOCTYPE fontconfig SYSTEM "fonts.dtd">' >> /etc/fonts/conf.d/99-custom-fonts.conf && \
    echo '<fontconfig><dir>/app/fonts</dir></fontconfig>' >> /etc/fonts/conf.d/99-custom-fonts.conf && \
    fc-cache -f -v

RUN mkdir -p public

EXPOSE 10000

CMD ["python", "main.py"]