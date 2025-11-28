# Data Directory

## Required File

Place `synthetic_fb_ads_undergarments.csv` in the project root directory.

The file should be located at:
```
kasparro/synthetic_fb_ads_undergarments.csv
```

## Expected Schema

The CSV should contain the following columns:

| Column | Type | Description |
|--------|------|-------------|
| `campaign_name` | string | Facebook campaign name |
| `adset_name` | string | Ad set name |
| `date` | date | Date (YYYY-MM-DD format) |
| `spend` | float | Daily ad spend in currency |
| `impressions` | int | Number of impressions |
| `clicks` | int | Number of clicks |
| `ctr` | float | Click-through rate (0.0 to 1.0) |
| `purchases` | int | Number of purchases/conversions |
| `revenue` | float | Revenue generated |
| `roas` | float | Return on ad spend (revenue/spend) |
| `creative_type` | string | Type of creative (Image, Video, UGC, Carousel) |
| `creative_message` | string | Ad copy/messaging text |
| `audience_type` | string | Audience targeting type (Broad, Lookalike, Retargeting) |
| `platform` | string | Platform (Facebook, Instagram) |
| `country` | string | Country code (US, UK, IN, etc.) |

## Sample Data

```csv
campaign_name,adset_name,date,spend,impressions,clicks,ctr,purchases,revenue,roas,creative_type,creative_message,audience_type,platform,country
Men ComfortMax Launch,Adset-1 Retarget,2025-01-01,640.09,235597,4313,0.0183,80,1514.28,2.37,Image,Breathable organic cotton that moves with you,Broad,Facebook,US
```

## Data Quality Notes

The data loader handles:
- **Missing values**: Fills with 0 for numeric metrics
- **Date parsing**: Converts string dates to datetime
- **Name normalization**: Cleans campaign names (removes extra spaces, inconsistent caps)
- **Derived metrics**: Recalculates CTR and ROAS from base metrics

## Sample Mode

For testing with a smaller dataset:

1. Edit `config/config.yaml`:
```yaml
data:
  use_sample: true
  sample_size: 1000
```

2. Or create a smaller sample manually:
```python
import pandas as pd
df = pd.read_csv('synthetic_fb_ads_undergarments.csv')
sample = df.sample(n=1000, random_state=42)
sample.to_csv('data/sample_fb_ads.csv', index=False)
```

Then update config:
```yaml
data:
  csv_path: "data/sample_fb_ads.csv"
```
