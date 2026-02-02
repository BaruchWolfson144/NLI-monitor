# הגדרת Google Cloud Platform

מדריך צעד אחר צעד להתקנת המערכת ב-GCP.

## דרישות מוקדמות

- חשבון Google Cloud עם פרויקט קיים
- `gcloud` CLI מותקן על המחשב
- מפתחות ה-API הבאים:
  - Google Places API key
  - Telegram Bot token
  - Telegram Chat ID

## שלב 1: הגדרת gcloud

```bash
# התחברות
gcloud auth login

# הגדרת פרויקט ברירת מחדל
gcloud config set project YOUR_PROJECT_ID

# הפעלת APIs נדרשים
gcloud services enable \
    cloudfunctions.googleapis.com \
    cloudscheduler.googleapis.com \
    secretmanager.googleapis.com \
    storage.googleapis.com \
    cloudbuild.googleapis.com
```

## שלב 2: יצירת Secrets

```bash
# יצירת ה-secrets
echo -n "YOUR_GOOGLE_API_KEY" | gcloud secrets create GOOGLE_API_KEY --data-file=-
echo -n "YOUR_TELEGRAM_BOT_TOKEN" | gcloud secrets create TELEGRAM_BOT_TOKEN --data-file=-
echo -n "@your_channel_name" | gcloud secrets create TELEGRAM_CHAT_ID --data-file=-
echo -n "ChIJy8LxJaZGHRURzNVZXycuQnw" | gcloud secrets create PLACE_ID --data-file=-
```

**חשוב**: החלף את הערכים למפתחות האמיתיים שלך.

## שלב 3: הרשאות ל-Cloud Function

```bash
PROJECT_ID=$(gcloud config get-value project)
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')

# הרשאת גישה ל-secrets
gcloud secrets add-iam-policy-binding GOOGLE_API_KEY \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding TELEGRAM_BOT_TOKEN \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding TELEGRAM_CHAT_ID \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding PLACE_ID \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

## שלב 4: הרצת הדיפלוי

```bash
# הגדרת משתני סביבה
export GCP_PROJECT=YOUR_PROJECT_ID
export GCP_REGION=me-west1  # או אזור אחר
export BUCKET_NAME=nli-monitor-data

# הרצת סקריפט הדיפלוי
./scripts/deploy.sh
```

## שלב 5: בדיקה

```bash
# בדיקה ידנית
curl "$(gcloud functions describe monitor-crowds --region=me-west1 --gen2 --format='value(serviceConfig.uri)')"

# צפייה בלוגים
gcloud functions logs read monitor-crowds --region=me-west1 --gen2 --limit=50
```

## פתרון בעיות

### שגיאת הרשאות ל-secrets
```bash
# בדיקת הרשאות
gcloud secrets get-iam-policy GOOGLE_API_KEY
```

### הפונקציה לא נקראת
```bash
# בדיקת סטטוס ה-scheduler
gcloud scheduler jobs describe trigger-monitor-crowds --location=me-west1

# הפעלה ידנית
gcloud scheduler jobs run trigger-monitor-crowds --location=me-west1
```

### בדיקת Cloud Storage
```bash
# צפייה בקבצים
gsutil ls gs://nli-monitor-data/
gsutil ls gs://nli-monitor-data/readings/
```

## עלויות צפויות

| שירות | שימוש | עלות |
|--------|-------|------|
| Cloud Functions | ~1,500 invocations/month | $0 (free tier) |
| Cloud Scheduler | 2 jobs | $0 (free tier) |
| Cloud Storage | < 1MB | $0 (free tier) |
| Secret Manager | 4 secrets | $0 (free tier) |

**סה"כ צפוי: $0/month**
