# FeatureGuard nginx reverse proxy - bakes nginx.conf into the image (build context = repo root)
FROM nginx:1.27-alpine

COPY nginx/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
