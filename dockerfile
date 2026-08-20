# Step 1: Extract Kaniko binaries from the official debug image
FROM gcr.io/kaniko-project/executor:debug 

# Jenkins durable-task invokes these utilities by their conventional paths.
RUN ["/busybox/sh", "-c", "mkdir -p /bin \
    && ln -sf /busybox/sh /bin/sh \
    && ln -sf /busybox/nohup /bin/nohup \
    && ln -sf /busybox/touch /bin/touch \
    && ln -sf /busybox/cp /bin/cp \
    && ln -sf /busybox/mv /bin/mv"]

ENV PATH="/bin:/usr/local/bin:/kaniko:/busybox"

# Kaniko needs root while unpacking base-image layers that preserve ownership
# metadata (for example, Python's system users). Pod fsGroup keeps its shared
# Jenkins workspace and Docker auth volume writable without privileged mode.