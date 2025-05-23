import numpy as np
import pytest
from numpy.testing import assert_allclose
from scipy.integrate import trapezoid

from sklearn import clone
from sklearn.compose import make_column_transformer
from sklearn.datasets import load_breast_cancer, make_classification
from sklearn.exceptions import NotFittedError
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import RocCurveDisplay, auc, roc_curve
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.utils import shuffle


@pytest.fixture(scope="module")
def data_binary():
    X, y = make_classification(
        n_samples=200,
        n_features=20,
        n_informative=5,
        n_redundant=2,
        flip_y=0.1,
        class_sep=0.8,
        random_state=42,
    )
    return X, y


@pytest.mark.parametrize("response_method", ["predict_proba", "decision_function"])
@pytest.mark.parametrize("with_sample_weight", [True, False])
@pytest.mark.parametrize("drop_intermediate", [True, False])
@pytest.mark.parametrize("with_strings", [True, False])
@pytest.mark.parametrize(
    "constructor_name, default_name",
    [
        ("from_estimator", "LogisticRegression"),
        ("from_predictions", "Classifier"),
    ],
)
def test_roc_curve_display_plotting(
    pyplot,
    response_method,
    data_binary,
    with_sample_weight,
    drop_intermediate,
    with_strings,
    constructor_name,
    default_name,
):
    """Check the overall plotting behaviour."""
    X, y = data_binary

    pos_label = None
    if with_strings:
        y = np.array(["c", "b"])[y]
        pos_label = "c"

    if with_sample_weight:
        rng = np.random.RandomState(42)
        sample_weight = rng.randint(1, 4, size=(X.shape[0]))
    else:
        sample_weight = None

    lr = LogisticRegression()
    lr.fit(X, y)

    y_score = getattr(lr, response_method)(X)
    y_score = y_score if y_score.ndim == 1 else y_score[:, 1]

    if constructor_name == "from_estimator":
        display = RocCurveDisplay.from_estimator(
            lr,
            X,
            y,
            sample_weight=sample_weight,
            drop_intermediate=drop_intermediate,
            pos_label=pos_label,
            alpha=0.8,
        )
    else:
        display = RocCurveDisplay.from_predictions(
            y,
            y_score,
            sample_weight=sample_weight,
            drop_intermediate=drop_intermediate,
            pos_label=pos_label,
            alpha=0.8,
        )

    fpr, tpr, _ = roc_curve(
        y,
        y_score,
        sample_weight=sample_weight,
        drop_intermediate=drop_intermediate,
        pos_label=pos_label,
    )

    assert_allclose(display.roc_auc, auc(fpr, tpr))
    assert_allclose(display.fpr, fpr)
    assert_allclose(display.tpr, tpr)

    assert display.estimator_name == default_name

    import matplotlib as mpl

    assert isinstance(display.line_, mpl.lines.Line2D)
    assert display.line_.get_alpha() == 0.8
    assert isinstance(display.ax_, mpl.axes.Axes)
    assert isinstance(display.figure_, mpl.figure.Figure)
    assert display.ax_.get_adjustable() == "box"
    assert display.ax_.get_aspect() in ("equal", 1.0)
    assert display.ax_.get_xlim() == display.ax_.get_ylim() == (-0.01, 1.01)

    expected_label = f"{default_name} (AUC = {display.roc_auc:.2f})"
    assert display.line_.get_label() == expected_label

    expected_pos_label = 1 if pos_label is None else pos_label
    expected_ylabel = f"True Positive Rate (Positive label: {expected_pos_label})"
    expected_xlabel = f"False Positive Rate (Positive label: {expected_pos_label})"

    assert display.ax_.get_ylabel() == expected_ylabel
    assert display.ax_.get_xlabel() == expected_xlabel


@pytest.mark.parametrize("plot_chance_level", [True, False])
@pytest.mark.parametrize("label", [None, "Test Label"])
@pytest.mark.parametrize(
    "chance_level_kw",
    [
        None,
        {"linewidth": 1, "color": "red", "linestyle": "-", "label": "DummyEstimator"},
        {"lw": 1, "c": "red", "ls": "-", "label": "DummyEstimator"},
        {"lw": 1, "color": "blue", "ls": "-", "label": None},
    ],
)
@pytest.mark.parametrize(
    "constructor_name",
    ["from_estimator", "from_predictions"],
)
def test_roc_curve_chance_level_line(
    pyplot,
    data_binary,
    plot_chance_level,
    chance_level_kw,
    label,
    constructor_name,
):
    """Check the chance level line plotting behaviour."""
    X, y = data_binary

    lr = LogisticRegression()
    lr.fit(X, y)

    y_score = getattr(lr, "predict_proba")(X)
    y_score = y_score if y_score.ndim == 1 else y_score[:, 1]

    if constructor_name == "from_estimator":
        display = RocCurveDisplay.from_estimator(
            lr,
            X,
            y,
            label=label,
            alpha=0.8,
            plot_chance_level=plot_chance_level,
            chance_level_kw=chance_level_kw,
        )
    else:
        display = RocCurveDisplay.from_predictions(
            y,
            y_score,
            label=label,
            alpha=0.8,
            plot_chance_level=plot_chance_level,
            chance_level_kw=chance_level_kw,
        )

    import matplotlib as mpl

    assert isinstance(display.line_, mpl.lines.Line2D)
    assert display.line_.get_alpha() == 0.8
    assert isinstance(display.ax_, mpl.axes.Axes)
    assert isinstance(display.figure_, mpl.figure.Figure)

    if plot_chance_level:
        assert isinstance(display.chance_level_, mpl.lines.Line2D)
        assert tuple(display.chance_level_.get_xdata()) == (0, 1)
        assert tuple(display.chance_level_.get_ydata()) == (0, 1)
    else:
        assert display.chance_level_ is None

    # Checking for chance level line styles
    if plot_chance_level and chance_level_kw is None:
        assert display.chance_level_.get_color() == "k"
        assert display.chance_level_.get_linestyle() == "--"
        assert display.chance_level_.get_label() == "Chance level (AUC = 0.5)"
    elif plot_chance_level:
        if "c" in chance_level_kw:
            assert display.chance_level_.get_color() == chance_level_kw["c"]
        else:
            assert display.chance_level_.get_color() == chance_level_kw["color"]
        if "lw" in chance_level_kw:
            assert display.chance_level_.get_linewidth() == chance_level_kw["lw"]
        else:
            assert display.chance_level_.get_linewidth() == chance_level_kw["linewidth"]
        if "ls" in chance_level_kw:
            assert display.chance_level_.get_linestyle() == chance_level_kw["ls"]
        else:
            assert display.chance_level_.get_linestyle() == chance_level_kw["linestyle"]
        # Checking for legend behaviour
        if label is not None or chance_level_kw.get("label") is not None:
            legend = display.ax_.get_legend()
            assert legend is not None  #  Legend should be present if any label is set
            legend_labels = [text.get_text() for text in legend.get_texts()]
            if label is not None:
                assert label in legend_labels
            if chance_level_kw.get("label") is not None:
                assert chance_level_kw["label"] in legend_labels
        else:
            assert display.ax_.get_legend() is None


@pytest.mark.parametrize(
    "clf",
    [
        LogisticRegression(),
        make_pipeline(StandardScaler(), LogisticRegression()),
        make_pipeline(
            make_column_transformer((StandardScaler(), [0, 1])), LogisticRegression()
        ),
    ],
)
@pytest.mark.parametrize("constructor_name", ["from_estimator", "from_predictions"])
def test_roc_curve_display_complex_pipeline(pyplot, data_binary, clf, constructor_name):
    """Check the behaviour with complex pipeline."""
    X, y = data_binary

    clf = clone(clf)

    if constructor_name == "from_estimator":
        with pytest.raises(NotFittedError):
            RocCurveDisplay.from_estimator(clf, X, y)

    clf.fit(X, y)

    if constructor_name == "from_estimator":
        display = RocCurveDisplay.from_estimator(clf, X, y)
        name = clf.__class__.__name__
    else:
        display = RocCurveDisplay.from_predictions(y, y)
        name = "Classifier"

    assert name in display.line_.get_label()
    assert display.estimator_name == name


@pytest.mark.parametrize(
    "roc_auc, estimator_name, expected_label",
    [
        (0.9, None, "AUC = 0.90"),
        (None, "my_est", "my_est"),
        (0.8, "my_est2", "my_est2 (AUC = 0.80)"),
    ],
)
def test_roc_curve_display_default_labels(
    pyplot, roc_auc, estimator_name, expected_label
):
    """Check the default labels used in the display."""
    fpr = np.array([0, 0.5, 1])
    tpr = np.array([0, 0.5, 1])
    disp = RocCurveDisplay(
        fpr=fpr, tpr=tpr, roc_auc=roc_auc, estimator_name=estimator_name
    ).plot()
    assert disp.line_.get_label() == expected_label


@pytest.mark.parametrize("response_method", ["predict_proba", "decision_function"])
@pytest.mark.parametrize("constructor_name", ["from_estimator", "from_predictions"])
def test_plot_roc_curve_pos_label(pyplot, response_method, constructor_name):
    # check that we can provide the positive label and display the proper
    # statistics
    X, y = load_breast_cancer(return_X_y=True)
    # create an highly imbalanced
    idx_positive = np.flatnonzero(y == 1)
    idx_negative = np.flatnonzero(y == 0)
    idx_selected = np.hstack([idx_negative, idx_positive[:25]])
    X, y = X[idx_selected], y[idx_selected]
    X, y = shuffle(X, y, random_state=42)
    # only use 2 features to make the problem even harder
    X = X[:, :2]
    y = np.array(["cancer" if c == 1 else "not cancer" for c in y], dtype=object)
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        stratify=y,
        random_state=0,
    )

    classifier = LogisticRegression()
    classifier.fit(X_train, y_train)

    # sanity check to be sure the positive class is classes_[0] and that we
    # are betrayed by the class imbalance
    assert classifier.classes_.tolist() == ["cancer", "not cancer"]

    y_score = getattr(classifier, response_method)(X_test)
    # we select the corresponding probability columns or reverse the decision
    # function otherwise
    y_score_cancer = -1 * y_score if y_score.ndim == 1 else y_score[:, 0]
    y_score_not_cancer = y_score if y_score.ndim == 1 else y_score[:, 1]

    if constructor_name == "from_estimator":
        display = RocCurveDisplay.from_estimator(
            classifier,
            X_test,
            y_test,
            pos_label="cancer",
            response_method=response_method,
        )
    else:
        display = RocCurveDisplay.from_predictions(
            y_test,
            y_score_cancer,
            pos_label="cancer",
        )

    roc_auc_limit = 0.95679

    assert display.roc_auc == pytest.approx(roc_auc_limit)
    assert trapezoid(display.tpr, display.fpr) == pytest.approx(roc_auc_limit)

    if constructor_name == "from_estimator":
        display = RocCurveDisplay.from_estimator(
            classifier,
            X_test,
            y_test,
            response_method=response_method,
            pos_label="not cancer",
        )
    else:
        display = RocCurveDisplay.from_predictions(
            y_test,
            y_score_not_cancer,
            pos_label="not cancer",
        )

    assert display.roc_auc == pytest.approx(roc_auc_limit)
    assert trapezoid(display.tpr, display.fpr) == pytest.approx(roc_auc_limit)


# TODO(1.9): remove
def test_y_score_and_y_pred_specified_error():
    """Check that an error is raised when both y_score and y_pred are specified."""
    y_true = np.array([0, 1, 1, 0])
    y_score = np.array([0.1, 0.4, 0.35, 0.8])
    y_pred = np.array([0.2, 0.3, 0.5, 0.1])

    with pytest.raises(
        ValueError, match="`y_pred` and `y_score` cannot be both specified"
    ):
        RocCurveDisplay.from_predictions(y_true, y_score=y_score, y_pred=y_pred)


# TODO(1.9): remove
def test_y_pred_deprecation_warning(pyplot):
    """Check that a warning is raised when y_pred is specified."""
    y_true = np.array([0, 1, 1, 0])
    y_score = np.array([0.1, 0.4, 0.35, 0.8])

    with pytest.warns(FutureWarning, match="y_pred is deprecated in 1.7"):
        display_y_pred = RocCurveDisplay.from_predictions(y_true, y_pred=y_score)

    assert_allclose(display_y_pred.fpr, [0, 0.5, 0.5, 1])
    assert_allclose(display_y_pred.tpr, [0, 0, 1, 1])

    display_y_score = RocCurveDisplay.from_predictions(y_true, y_score)
    assert_allclose(display_y_score.fpr, [0, 0.5, 0.5, 1])
    assert_allclose(display_y_score.tpr, [0, 0, 1, 1])


@pytest.mark.parametrize("despine", [True, False])
@pytest.mark.parametrize("constructor_name", ["from_estimator", "from_predictions"])
def test_plot_roc_curve_despine(pyplot, data_binary, despine, constructor_name):
    # Check that the despine keyword is working correctly
    X, y = data_binary

    lr = LogisticRegression().fit(X, y)
    lr.fit(X, y)

    y_pred = lr.decision_function(X)

    # safe guard for the binary if/else construction
    assert constructor_name in ("from_estimator", "from_predictions")

    if constructor_name == "from_estimator":
        display = RocCurveDisplay.from_estimator(lr, X, y, despine=despine)
    else:
        display = RocCurveDisplay.from_predictions(y, y_pred, despine=despine)

    for s in ["top", "right"]:
        assert display.ax_.spines[s].get_visible() is not despine

    if despine:
        for s in ["bottom", "left"]:
            assert display.ax_.spines[s].get_bounds() == (0, 1)
