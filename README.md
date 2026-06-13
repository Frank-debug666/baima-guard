# Baima Guard / 白马卫士

> 白马伴您身旁，为爱守护

[简体中文说明](README.zh-CN.md)

Baima Guard is an educational Chinese SMS risk detection platform. It combines a character-level RNN, explainable multi-signal risk policies, and persistent user feedback correction.

![Baima Guard dashboard](docs/screenshot.png)

## Why This Project

A standalone classifier can perform well on familiar test data but still miss novel scam language. For example, the base RNN assigned a very low risk score to a joke-style scam asking the recipient to fund the restoration of the Qin dynasty.

Baima Guard uses a hybrid design:

- **RNN model** for a baseline risk probability.
- **Explainable risk policy** for combinations such as money request + secrecy + urgency.
- **Persistent feedback learning** to correct identical or similar messages after user feedback.

## Features

- Single-message and batch risk detection
- Risk probability, category, evidence, and suggested action
- Explainable scam-pattern detection
- Persistent false-positive and false-negative correction
- Detection history and model metrics dashboard
- FastAPI backend and React frontend
- Windows one-click setup
- Optional Codex Skill in `skills/detect-chinese-sms-risk`

## Architecture

```text
React UI
   |
FastAPI /api/predict
   |
   +-- Character-level RNN
   +-- Multi-signal risk policy
   +-- Persistent feedback similarity matching
   |
Risk score + evidence + suggested action
```

## Model

```text
characters -> token IDs -> Embedding(64) -> RNN(64) -> Linear(2) -> Softmax
```

Reported metrics for the included baseline checkpoint:

| Metric | Value |
|---|---:|
| Test accuracy | 94.8% |
| Risk recall | 92.6% |
| Normal-message false-positive rate | 4.9% |
| Calibrated risk threshold | 0.83 |

These are baseline RNN metrics from the original project split. They are not production guarantees and do not measure the complete hybrid system on live traffic.

## Quick Start

### Windows

Requirements:

- Python 3.10+
- Node.js 20.19+

Double-click:

```text
start_windows.bat
```

Then open <http://127.0.0.1:8000>.

### Manual Setup

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-api.txt

cd frontend
npm install
npm run build
cd ..

.venv/Scripts/python -m uvicorn api_server:app --host 0.0.0.0 --port 8000
```

On Linux/macOS, replace `.venv/Scripts/python` with `.venv/bin/python`.

## API

### Predict

```bash
curl -X POST http://127.0.0.1:8000/api/predict \
  -H "Content-Type: application/json" \
  -d "{\"text\":\"我是秦始皇，转我五十万，这个消息只告诉你一个人，速度！\"}"
```

### Save Feedback

```bash
curl -X POST http://127.0.0.1:8000/api/feedback \
  -H "Content-Type: application/json" \
  -d "{\"text\":\"message\",\"predicted_class\":1,\"is_correct\":false}"
```

Feedback is stored locally in `feedback_store.json`, which is ignored by Git.

## Training

The original raw SMS dataset is intentionally not published because it contains phone numbers, links, email addresses, and text with unclear redistribution rights.

`data/sms_samples.tsv` contains a tiny synthetic, privacy-safe example. Replace it with your own licensed dataset before training:

```text
0<TAB>normal message
1<TAB>risk message
```

Then run:

```bash
python train_api_model.py
```

## Tests

```bash
run_tests.bat
```

Or:

```bash
python -m py_compile api_model.py api_server.py train_api_model.py
python -c "from test_risk_policy import test_high_risk_combinations,test_normal_messages_do_not_trigger_policy; test_high_risk_combinations(); test_normal_messages_do_not_trigger_policy()"
python test_feedback_learning.py
```

## Codex Skill

The optional Skill can analyze Chinese messages without running the web UI:

```bash
python skills/detect-chinese-sms-risk/scripts/predict_sms.py "老板换号了，马上转给我三万元，不要告诉财务。"
```

Install the `skills/detect-chinese-sms-risk` directory into your Codex skills folder to invoke `$detect-chinese-sms-risk`.

## Limitations

- The RNN has limited semantic generalization compared with modern pretrained models.
- Rule scores are heuristic and not statistically calibrated.
- Similarity-based feedback correction is not online neural-network training.
- JSON persistence is designed for local demos, not multi-instance production.
- A production system needs authentication, review workflows, database storage, monitoring, privacy controls, and independent evaluation.

## Privacy and Responsible Use

- Do not upload private messages or personal data without authorization.
- Do not treat results as definitive evidence of fraud.
- Use risk results as decision support and preserve a human review path.
- The included code and checkpoint are provided for education and demonstration.

## License

MIT
