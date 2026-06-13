import tempfile
from pathlib import Path

import api_server


def run_feedback_learning_test():
    original_path = api_server.FEEDBACK_PATH
    try:
        with tempfile.TemporaryDirectory() as directory:
            api_server.FEEDBACK_PATH = Path(directory) / "feedback_store.json"
            text = "公司通知，今晚十点需要系统维护。"
            normalized = api_server.normalize_text(text)
            api_server.save_feedback([{
                "text": text,
                "normalized_text": normalized,
                "predicted_class": 1,
                "corrected_class": 0,
                "is_correct": False,
            }])

            exact = api_server.feedback_override(text)
            similar = api_server.feedback_override("公司通知：今晚十点进行系统维护，请知悉。")
            assert exact["class_id"] == 0
            assert similar["class_id"] == 0
            assert api_server.load_feedback()[0]["normalized_text"] == normalized
    finally:
        api_server.FEEDBACK_PATH = original_path


if __name__ == "__main__":
    run_feedback_learning_test()
    print("feedback learning test passed")
