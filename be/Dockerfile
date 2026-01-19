# 1. שימוש בתמונת הבסיס של AWS Lambda
FROM public.ecr.aws/lambda/python:3.11

# 2. העתקת קובץ הדרישות
# שים לב: אם לקובץ שלך קוראים req.txt תשאיר ככה, אם requirements.txt - תשנה כאן!
COPY req.txt ${LAMBDA_TASK_ROOT}

# 3. התקנת הספריות
# הורדתי את --only-binary כדי למנוע שגיאות התקנה עם ספריות AI
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r req.txt

# 4. העתקת כל הקוד
COPY . ${LAMBDA_TASK_ROOT}

# 5. הרצת ה-Handler שהגדרנו ב-main.py
CMD [ "main.handler" ]