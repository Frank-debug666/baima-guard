@echo off
setlocal
cd /d "%~dp0"
python -m py_compile api_model.py api_server.py train_api_model.py
python -c "from test_risk_policy import test_high_risk_combinations,test_normal_messages_do_not_trigger_policy; test_high_risk_combinations(); test_normal_messages_do_not_trigger_policy()"
python test_feedback_learning.py
