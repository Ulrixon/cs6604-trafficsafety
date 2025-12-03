# VDOT 511 API Access Request

## Overview

To enable camera lookup functionality, you need API access to the VDOT 511 traffic camera system. This document outlines the request process and setup instructions.

## Access Request

### Contact Information

**Email:** 511_videosubscription@iteris.com
**Provider:** Iteris Inc. (contracted by VDOT)
**Documentation:** https://www.virginiadot.org/newsroom/511_video.asp

### Email Template

```
Subject: VDOT 511 API Access Request - Traffic Safety Index System

Dear VDOT 511 Video Subscription Team,

I am writing to request API access to the VDOT 511 traffic camera feeds for our Traffic Safety Index System.

Organization: [Your Organization Name]
Contact Name: [Your Name]
Email: [Your Email]
Phone: [Your Phone]

Use Case:
We are developing a traffic safety analysis system that combines real-time traffic data with safety indices for Virginia intersections. We would like to integrate traffic camera feeds to allow engineers and traffic analysts to visually verify intersection conditions when investigating safety events.

The camera feeds will be used for internal analysis purposes and will be made available to authorized users (traffic engineers, safety analysts) through our web-based dashboard application.

Distribution: Internal use only (not for resale)

Please provide:
1. API key for authentication
2. API endpoint documentation
3. Rate limits and usage guidelines
4. Any terms of use or user agreements

Thank you for your consideration.

Best regards,
[Your Name]
[Your Title]
```

## Setup Instructions

### 1. Environment Variables

Once you receive your API key, configure the following environment variables:

```bash
# Required
export VDOT_API_KEY="your-api-key-here"

# Optional (with defaults)
export VDOT_API_URL="https://api.vdot.virginia.gov/511"  # Default
export VDOT_CACHE_TTL="300"  # Cache duration in seconds (5 minutes)
```

### 2. Docker/Cloud Run Configuration

For containerized deployments, add to your environment configuration:

**docker-compose.yml:**
```yaml
services:
  backend:
    environment:
      - VDOT_API_KEY=${VDOT_API_KEY}
      - VDOT_API_URL=https://api.vdot.virginia.gov/511
      - VDOT_CACHE_TTL=300
```

**Google Cloud Run:**
```bash
gcloud run services update trafficsafety-api \
  --update-env-vars VDOT_API_KEY=your-key-here,VDOT_API_URL=https://api.vdot.virginia.gov/511,VDOT_CACHE_TTL=300
```

### 3. Local Development

For local testing without API access:

```bash
# Camera service will gracefully degrade to 511 map links only
# No API key needed - service will log warning but continue to work
```

### 4. Verify Setup

Test your API configuration:

```python
from app.services.vdot_camera_service import VDOTCameraService

service = VDOTCameraService()

# Test camera lookup (Blacksburg, VA example)
cameras = service.find_nearest_cameras(37.2296, -80.4139, radius_miles=1.0)

print(f"Found {len(cameras)} camera(s)")
for cam in cameras:
    print(f"  - {cam['label']}: {cam['url']}")
```

Expected output (with valid API key):
```
Found 2 camera(s)
  - VDOT I-81 @ Exit 118: https://511virginia.org/camera/CAM456
  - VDOT US-460 @ Main St: https://511virginia.org/camera/CAM789
```

## Pricing

- **Internal Use (Free):** Free for internal use or free distribution to the public (e.g., through media)
- **Resale (Paid):** Monthly fee for commercial redistribution (e.g., multi-state video redistributors)

For this application, **internal use pricing** applies (free).

## API Capabilities

### Expected Response Format

```json
{
  "cameras": [
    {
      "id": "CAM123",
      "name": "I-95 @ Exit 74",
      "latitude": 37.5407,
      "longitude": -77.4360,
      "description": "Interstate 95 Northbound at Exit 74",
      "url": "https://511virginia.org/camera/CAM123"
    }
  ]
}
```

### Rate Limits

(To be confirmed with Iteris - typically 100-1000 requests/minute)

### Caching Strategy

The `VDOTCameraService` implements caching to minimize API calls:
- **Cache Duration:** 5 minutes (configurable via `VDOT_CACHE_TTL`)
- **Cache Type:** LRU cache with maxsize=1 (single camera list cached)
- **Invalidation:** Automatic after TTL expires

This reduces API load from potentially thousands of requests/hour to ~12 requests/hour.

## Fallback Behavior

If VDOT API is unavailable or no cameras are found:
- Service returns empty camera list
- Frontend displays 511 map link as fallback
- Users can still view general traffic conditions on VDOT 511 website

## Support

### VDOT Support
- **Email:** 511_videosubscription@iteris.com
- **Website:** https://www.virginiadot.org/newsroom/511_video.asp

### Application Support
- Check service logs for API errors
- Verify `VDOT_API_KEY` is set correctly
- Test with `VDOTCameraService` directly before troubleshooting frontend

## Security

- **DO NOT commit API keys to Git**
- Use environment variables or secret management services
- Rotate API keys periodically (if provided by VDOT)
- Monitor API usage for unexpected spikes

## Monitoring

Key metrics to track:
- API response times (should be < 1 second)
- API error rates (should be < 1%)
- Cache hit rate (should be > 80%)
- Cameras found rate (varies by location)

Add monitoring with logging:
```python
logger.info(f"VDOT API: {len(cameras)} cameras, {response_time_ms}ms")
```

## Next Steps

1. Send access request email to Iteris
2. Wait for API key (typically 1-2 business days)
3. Configure environment variables
4. Test camera service
5. Deploy to production
6. Monitor usage and performance

## FAQ

**Q: What if the API key request is denied?**
A: The system will still work - users will see 511 map links instead of specific cameras.

**Q: Can we cache camera locations permanently?**
A: No - cameras can be added, moved, or removed. Keep cache TTL at 5 minutes.

**Q: Do we need separate keys for dev/staging/prod?**
A: Ask Iteris - some providers issue one key, others provide separate keys per environment.

**Q: What if cameras are offline?**
A: VDOT API should filter offline cameras. If not, users will see "camera unavailable" on VDOT website.
