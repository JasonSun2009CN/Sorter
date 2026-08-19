# =============================================================================
# tests/test_training.py —— 训练数据管理
# =============================================================================

from app.database import Database
from app.ml import training


def _db(tmp_path):
    db = Database(tmp_path / "test.db")
    db.initialize()
    return db


def test_save_and_load_correction(tmp_path):
    db = _db(tmp_path)
    fid = db.insert_file(
        path=str(tmp_path / "a.pdf"), name="a.pdf", extension=".pdf",
        size=1, mtime=0.0, ctime=0.0,
    )
    training.save_correction(db, fid, "math")
    training.save_correction(db, fid, "school")
    training.save_correction(db, fid, "bad", accepted=False)

    data = training.load_training_data(db)
    assert len(data) == 1
    file_, tags = data[0]
    assert tags == {"math", "school"}  # 拒绝样本不计入
    assert file_.path.name == "a.pdf"


def test_save_same_pair_overwrites(tmp_path):
    db = _db(tmp_path)
    fid = db.insert_file(
        path=str(tmp_path / "a.pdf"), name="a.pdf", extension=".pdf",
        size=1, mtime=0.0, ctime=0.0,
    )
    training.save_correction(db, fid, "math")
    training.save_correction(db, fid, "math")  # 覆盖，不新增
    data = training.load_training_data(db)
    assert len(data) == 1
    assert data[0][1] == {"math"}


def test_load_reconstructs_file_from_db_row(tmp_path):
    """即使源文件已删除，仍能按 DB 行重建 ScannedFile。"""
    db = _db(tmp_path)
    p = tmp_path / "gone.txt"
    p.write_text("x", encoding="utf-8")
    fid = db.insert_file(
        path=str(p), name="gone.txt", extension=".txt",
        size=1, mtime=0.0, ctime=0.0,
    )
    training.save_correction(db, fid, "math")
    p.unlink()
    data = training.load_training_data(db)
    assert len(data) == 1
    assert data[0][0].path.name == "gone.txt"


def test_retrain_aliases_train(tmp_path):
    import numpy as np
    from app.ml.classifier import TagClassifier

    X = np.random.RandomState(1).rand(4, 20)
    y = [{"a"}, {"b"}, {"a"}, {"b"}]
    clf = TagClassifier()
    retrained = training.retrain(clf, X, y)
    assert retrained is clf
    assert len(clf.classes_) == 2
