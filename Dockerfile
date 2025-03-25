# Use the micromamba Docker image
FROM mambaorg/micromamba:2.0.5

# Set working directory
WORKDIR /app

# Copy only environment.yml first to leverage Docker cache
COPY environment.yml /tmp/environment.yml

# Install dependencies
RUN micromamba create -y -n discord-bot -f /tmp/environment.yml && \
    micromamba clean --all --yes

# Ensure Conda environment is activated
ARG MAMBA_DOCKERFILE_ACTIVATE=1
ENV ENV_NAME=discord-bot

# Set environment variables
ENV PATH="/root/micromamba/bin:${PATH}"
ENV NEW_POSTS="10"
ENV USER_AGENT="python:seraph.discord.filterbot:v1.1.0 (by /u/RajinChicken)"
ENV PING_TIMER="600"

# Copy application code (after dependencies for better caching)
COPY . /app

# Add healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ps aux | grep "python bot.py" | grep -v grep > /dev/null || exit 1

# Specify the actual command to run your bot
CMD ["python", "bot.py"]