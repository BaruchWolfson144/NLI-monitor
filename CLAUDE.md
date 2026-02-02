# מערכת ניטור עומסים במוסדות תרבות

## סקירה כללית

מערכת לניטור עומסי קהל במוסדות תרבות בירושלים (~10 מקומות), עם שליחת עדכונים לערוץ טלגרם, ניתוח סטטיסטי וחיזוי ML.

## אילוצים

- **תקציב**: $0 - רק free tier
- **ממשק**: ערוץ טלגרם פסיבי (לא בוט אינטראקטיבי)
- **תשתית**: Google Cloud Functions + SQLite לוקלי

## ארכיטקטורה

```
┌─────────────────────────────────────────────────────────┐
│              CLOUD (Google Cloud Function)              │
│                                                         │
│  • Cloud Scheduler מפעיל כל 30 דקות                    │
│  • בודק עומס בכל המקומות (livepopulartimes)           │
│  • מעדכן טלגרם                                          │
│  • שומר readings ב-Cloud Storage (JSON)                │
└─────────────────────────┬───────────────────────────────┘
                          │
                          │ sync (כשהמחשב זמין)
                          ▼
┌─────────────────────────────────────────────────────────┐
│                LOCAL (מחשב המפתח)                       │
│                                                         │
│  • SQLite database (קובץ אחד)                          │
│  • סקריפט sync שמושך נתונים מ-Cloud Storage            │
│  • כלי ניתוח סטטיסטי                                   │
│  • אימון מודלים ML                                     │
└─────────────────────────────────────────────────────────┘
```

## מבנה הפרויקט

```
NLI_monitor/
├── functions/                  # Cloud Functions
│   └── collector/
│       ├── main.py            # הפונקציה הראשית
│       └── requirements.txt
├── local/                      # סקריפטים לוקליים
│   ├── database.py            # ניהול SQLite
│   ├── sync.py                # סנכרון מהענן
│   └── analytics.py           # ניתוח סטטיסטי
├── ml/                         # למידת מכונה
│   ├── train.py
│   └── models/
├── notebooks/                  # Jupyter notebooks
│   └── exploration.ipynb
├── data/                       # נתונים לוקליים
│   └── readings.db            # SQLite database
├── config/
│   └── locations.json         # רשימת מקומות לניטור
├── scripts/
│   └── deploy.sh              # סקריפט deployment
├── monitor.py                  # הסקריפט המקורי (legacy)
├── CLAUDE.md                   # מסמך זה
└── README.md
```

## סכמת Database (SQLite)

```sql
CREATE TABLE locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    name_he TEXT,
    place_id TEXT UNIQUE NOT NULL,
    address TEXT,
    operating_hours TEXT,  -- JSON string
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    location_id INTEGER REFERENCES locations(id),
    popularity INTEGER,  -- 0-100 or NULL
    timestamp TEXT NOT NULL,
    day_of_week INTEGER,
    hour INTEGER,
    is_open INTEGER
);
```

## שירותי Google Cloud

| שירות | שימוש | מכסה חינמית |
|--------|-------|-------------|
| Cloud Functions | הפונקציה הראשית | 2M/month |
| Cloud Scheduler | הפעלה כל 30 דק' | 3 jobs |
| Cloud Storage | אחסון readings | 5GB |
| Secret Manager | API keys | 6 secrets |

## Secrets נדרשים

- `GOOGLE_API_KEY` - Google Places API
- `TELEGRAM_BOT_TOKEN` - מ-BotFather
- `TELEGRAM_CHAT_ID` - ערוץ הטלגרם

## פקודות נפוצות

```bash
# Deploy Cloud Function
./scripts/deploy.sh

# Sync נתונים מהענן
python local/sync.py

# ניתוח סטטיסטי
python local/analytics.py
```

## שלבי פיתוח

1. **שלב 1**: מיגרציה לענן - Cloud Function + Scheduler
2. **שלב 2**: SQLite לוקלי + Sync
3. **שלב 3**: ניתוח סטטיסטי
4. **שלב 4**: למידת מכונה (אחרי 3-6 חודשי data)

## הערות חשובות

- ספריית `livepopulartimes` עושה scraping לא רשמי - עלולה להפסיק לעבוד
- הודעת טלגרם אחת מרוכזת לכל המקומות (edit, לא הודעות חדשות)
- גיבוי SQLite מומלץ ל-Google Drive
