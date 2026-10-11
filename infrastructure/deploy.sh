name: CI/CD Pipeline

on:
  push:
    branches:
      - main
      - feature/senior-architecture-refactor

jobs:
  quality-check:
    name: Code Quality & Typing
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          
      - name: Install validation tools
        run: pip install ruff mypy
        
      - name: Run Ruff (Linter)
        run: ruff check .
        
      - name: Run Mypy (Type Hinting)
        run: mypy src/ --ignore-missing-imports

  test:
    name: Unit & Integration Tests
    needs: quality-check
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15-alpine
        env:
          POSTGRES_USER: algo_user
          POSTGRES_PASSWORD: algo_password
          POSTGRES_DB: algo_test_db
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-asyncio httpx
          
      - name: Run tests
        env:
          DATABASE_URL: postgresql://algo_user:algo_password@localhost:5432/algo_test_db
        run: pytest tests/ -v

  deploy:
    name: Deploy to Kamatera
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main' || github.ref == 'refs/heads/feature/senior-architecture-refactor'
    steps:
      - name: Execute Remote SSH Commands
        uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.SERVER_IP }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          script: |
            cd ~/algo-trade-core
            git pull origin ${{ github.ref_name }}
            docker compose -f infrastructure/docker-compose.yml up --build -d
            docker system prune -af