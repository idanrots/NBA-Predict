FROM public.ecr.aws/lambda/python:3.11

COPY req.txt ${LAMBDA_TASK_ROOT}

# הוספנו את הדגל --only-binary=:all: וגם --upgrade
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --only-binary=:all: -r req.txt

COPY . ${LAMBDA_TASK_ROOT}

CMD [ "main.handler" ]