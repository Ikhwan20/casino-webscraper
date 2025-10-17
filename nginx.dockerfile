FROM nginx:alpine

# Remove default config
RUN rm /etc/nginx/conf.d/default.conf

# Copy custom config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Create directories
RUN mkdir -p /usr/share/nginx/html/output /usr/share/nginx/html/logs