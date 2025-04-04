# AUTOGENERATED! DO NOT EDIT! File to edit: ../../nbs/src/ets.ipynb.

# %% auto 0
__all__ = ['ets_f']

# %% ../../nbs/src/ets.ipynb 2
import math

import numpy as np
from statsmodels.tsa.seasonal import seasonal_decompose

from ._lib import ets as _ets
from .utils import _calculate_intervals, results

# %% ../../nbs/src/ets.ipynb 5
# Global variables
_smalno = np.finfo(float).eps
_PHI_LOWER = 0.8
_PHI_UPPER = 0.98

# %% ../../nbs/src/ets.ipynb 6
def etssimulate(
    x: np.ndarray,
    m: int,
    error: _ets.Component,
    trend: _ets.Component,
    season: _ets.Component,
    alpha: float,
    beta: float,
    gamma: float,
    phi: float,
    h: int,
    y: np.ndarray,
    e: np.ndarray,
) -> None:
    oldb = 0.0
    olds = np.zeros(24)
    s = np.zeros(24)
    f = np.zeros(10)
    if m > 24 and season != _ets.Component.Nothing:
        return
    elif m < 1:
        m = 1
    # Copy initial state components
    l = x[0]
    if trend != _ets.Component.Nothing:
        b = x[1]
    if season != _ets.Component.Nothing:
        for j in range(m):
            s[j] = x[(trend != _ets.Component.Nothing) + j + 1]
    for i in range(h):
        # Copy previous state
        oldl = l
        if trend != _ets.Component.Nothing:
            oldb = b
        if season != _ets.Component.Nothing:
            for j in range(m):
                olds[j] = s[j]
        # one step forecast
        _ets.forecast(
            f,
            oldl,
            oldb,
            olds,
            m,
            trend,
            season,
            phi,
            1,
        )
        if math.fabs(f[0] - _ets.NA) < _ets.TOL:
            y[0] = _ets.NA
            return
        if error == _ets.Component.Additive:
            y[i] = f[0] + e[i]
        else:
            y[i] = f[0] * (1.0 + e[i])
        # Update state
        l, b = _ets.update(
            s,
            l,
            b,
            oldl,
            oldb,
            olds,
            m,
            trend,
            season,
            alpha,
            beta,
            gamma,
            phi,
            y[i],
        )

# %% ../../nbs/src/ets.ipynb 7
def etsforecast(
    x: np.ndarray,
    m: int,
    trend: _ets.Component,
    season: _ets.Component,
    phi: float,
    h: int,
    f: np.ndarray,
) -> None:
    s = np.zeros(m, dtype=np.float64)
    if m < 1:
        m = 1
    # Copy initial state components
    l = x[0]
    b = 0.0
    has_trend = trend != _ets.Component.Nothing
    if has_trend:
        b = x[1]
    if season != _ets.Component.Nothing:
        s[:m] = x[has_trend + 1 : has_trend + 1 + m]
    # compute forecasts
    _ets.forecast(
        f,
        l,
        b,
        s,
        m,
        trend,
        season,
        phi,
        h,
    )

# %% ../../nbs/src/ets.ipynb 10
def initparam(
    alpha: float,
    beta: float,
    gamma: float,
    phi: float,
    trendtype: str,
    seasontype: str,
    damped: bool,
    lower: np.ndarray,
    upper: np.ndarray,
    m: int,
    bounds: str,
):
    if bounds == "admissible":
        lower[:3] = lower[:3] * 0
        upper[:3] = upper[:3] * 0 + 1e-3
    elif (lower > upper).any():
        raise Exception("Inconsistent parameter boundaries")
    # select alpha
    if np.isnan(alpha):
        alpha = lower[0] + 0.2 * (upper[0] - lower[0]) / m
        if alpha > 1 or alpha < 0:
            alpha = lower[0] + 2e-3
    # select beta
    if trendtype != "N" and np.isnan(beta):
        # ensure beta < alpha
        upper[1] = min(upper[1], alpha)
        beta = lower[1] + 0.1 * (upper[1] - lower[1])
        if beta < 0 or beta > alpha:
            beta = alpha - 1e-3
    # select gamma
    if seasontype != "N" and np.isnan(gamma):
        upper[2] = min(upper[2], 1 - alpha)
        gamma = lower[2] + 0.05 * (upper[2] - lower[2])
        if gamma < 0 or gamma > 1 - alpha:
            gamma = 1 - alpha - 1e-3
    # select phi
    if damped and np.isnan(phi):
        phi = lower[3] + 0.99 * (upper[3] - lower[3])
        if phi < 0 or phi > 1:
            phi = upper[3] - 1e-3
    return {"alpha": alpha, "beta": beta, "gamma": gamma, "phi": phi}

# %% ../../nbs/src/ets.ipynb 12
def admissible(alpha: float, beta: float, gamma: float, phi: float, m: int):
    if np.isnan(phi):
        phi = 1
    if phi < 0.0 or phi > 1 + 1e-8:
        return False
    if np.isnan(gamma):
        if alpha < 1 - 1 / phi or alpha > 1 + 1 / phi:
            return False
        if not np.isnan(beta):
            if beta < alpha * (phi - 1) or beta > (1 + phi) * (2 - alpha):
                return False
    elif m > 1:  # seasonal model
        if np.isnan(beta):
            beta = 0
        if gamma < max(1 - 1 / phi - alpha, 0) or gamma > 1 + 1 / phi - alpha:
            return False
        if alpha < 1 - 1 / phi - gamma * (1 - m + phi + phi * m) / (2 * phi * m):
            return False
        if beta < -(1 - phi) * (gamma / m + alpha):
            return False
        # End of easy test. Now use characteristic equation
        P = np.full(2 + m - 2 + 2, fill_value=np.nan)
        P[:2] = np.array(
            [phi * (1 - alpha - gamma), alpha + beta - alpha * phi + gamma - 1]
        )
        P[2 : (m - 2 + 2)] = np.repeat(alpha + beta - alpha * phi, m - 2)
        P[(m - 2 + 2) :] = np.array([alpha + beta - phi, 1])
        roots = np.polynomial.polynomial.polyroots(P)
        zeror = np.real(roots)
        zeroi = np.imag(roots)
        max_ = np.max(np.sqrt(zeror * zeror + zeroi * zeroi))
        if max_ > 1 + 1e-10:
            return False
    # passed all tests
    return True

# %% ../../nbs/src/ets.ipynb 13
def check_param(
    alpha: float,
    beta: float,
    gamma: float,
    phi: float,
    lower: np.ndarray,
    upper: np.ndarray,
    bounds: str,
    m: int,
):
    if bounds != "admissible":
        if not np.isnan(alpha):
            if alpha < lower[0] or alpha > upper[0]:
                return False
        if not np.isnan(beta):
            if beta < lower[1] or beta > alpha or beta > upper[1]:
                return False
        if not np.isnan(phi):
            if phi < lower[3] or phi > upper[3]:
                return False
        if not np.isnan(gamma):
            if gamma < lower[2] or gamma > 1 - alpha or gamma > upper[2]:
                return False
    if bounds != "usual":
        if not admissible(alpha, beta, gamma, phi, m):
            return False
    return True

# %% ../../nbs/src/ets.ipynb 14
def fourier(x, period, K, h=None):
    if h is None:
        times = np.arange(1, len(x) + 1)
    if h is not None:
        times = np.arange(len(x) + 1, len(x) + h + 1)
    # compute periods of all fourier terms
    # numba doesnt support list comprehension
    len_p = sum(K)
    p = np.full(len_p, fill_value=np.nan)
    idx = 0
    for j, p_ in enumerate(period):
        if K[j] > 0:
            p[idx : (idx + K[j])] = np.arange(1, K[j] + 1) / period[j]
            idx += K[j]
    p = np.unique(p)
    # Remove columns where sinpi=0
    k = np.abs(2 * p - np.round(2 * p, 0, np.empty_like(p))) > _smalno
    # Compute matrix of fourier terms
    X = np.full((len(times), 2 * len(p)), fill_value=np.nan)
    for j in range(len(p)):
        if k[j]:
            X[:, 2 * j - 1] = np.sin(2 * np.pi * p[j] * times)
        X[:, 2 * j] = np.cos(2 * np.pi * p[j] * times)
    X = X[:, ~np.isnan(X.sum(axis=0))]
    return X

# %% ../../nbs/src/ets.ipynb 16
def initstate(y, m, trendtype, seasontype):
    n = len(y)
    if seasontype != "N":
        if n < 4:
            raise ValueError("You've got to be joking (not enough data).")
        elif n < 3 * m:  # fit simple Fourier model
            fouriery = fourier(y, [m], [1])
            X_fourier = np.full((n, 4), fill_value=np.nan)
            X_fourier[:, 0] = np.ones(n)
            X_fourier[:, 1] = np.arange(1, n + 1)
            X_fourier[:, 2:4] = fouriery
            coefs, *_ = np.linalg.lstsq(X_fourier, y, rcond=-1)
            if seasontype == "A":
                y_d = dict(seasonal=y - coefs[0] - coefs[1] * X_fourier[:, 1])
            else:
                if not min(y) > 0:
                    raise Exception(
                        "Multiplicative seasonality is not appropriate for zero and negative values"
                    )
                y_d = dict(seasonal=y / (coefs[0] + coefs[1] * X_fourier[:, 1]))
        else:
            # n is large enough to do a decomposition
            y_d = seasonal_decompose(
                y, period=m, model="additive" if seasontype == "A" else "multiplicative"
            )
            y_d = dict(seasonal=y_d.seasonal)
        init_seas = y_d["seasonal"][1:m][::-1]
        if seasontype == "A":
            y_sa = y - y_d["seasonal"]
        else:
            init_seas = np.clip(init_seas, a_min=1e-2, a_max=None)
            if init_seas.sum() > m:
                init_seas = init_seas / np.sum(init_seas + 1e-2)
            y_sa = y / np.clip(y_d["seasonal"], a_min=1e-2, a_max=None)
    else:
        m = 1
        init_seas = []
        y_sa = y
    maxn = min(max(10, 2 * m), len(y_sa))
    if trendtype == "N":
        l0 = y_sa[:maxn].mean()
        b0 = None
        return np.concatenate([[l0], init_seas])
    else:  # simple linear regression on seasonally adjusted data
        X = np.full((n, 2), fill_value=np.nan)
        X[:, 0] = np.ones(n)
        X[:, 1] = np.arange(1, n + 1)
        (l, b), *_ = np.linalg.lstsq(X[:maxn], y_sa[:maxn], rcond=-1)
        if trendtype == "A":
            l0 = l
            b0 = b
            # if error type is M then we dont want l0+b0=0
            # so perturb just in case
            if abs(l0 + b0) < 1e-8:
                l0 = l0 * (1 + 1e-3)
                b0 = b0 * (1 - 1e-3)
        else:
            l0 = l + b
            if abs(l0) < 1e-8:
                l0 = 1e-7
            b0 = (l + 2 * b) / l0
            if math.isclose(b0, 0.0, abs_tol=1e-8):
                div = 1e-8
            else:
                div = b0
            l0 = l0 / div
            if abs(b0) > 1e10:
                b0 = np.sign(b0) * 1e10
            if l0 < 1e-8 or b0 < 1e-8:  # simple linear approximation didnt work
                l0 = max(y_sa[0], 1e-3)
                if math.isclose(y_sa[0], 0.0, abs_tol=1e-8):
                    div = 1e-8
                else:
                    div = y_sa[0]
                b0 = max(y_sa[1] / div, 1e-3)
    return np.concatenate([[l0, b0], init_seas])

# %% ../../nbs/src/ets.ipynb 20
def switch(x: str) -> _ets.Component:
    if x == "N":
        return _ets.Component.Nothing
    if x == "A":
        return _ets.Component.Additive
    if x == "M":
        return _ets.Component.Multiplicative
    raise ValueError(f"Unknown component {x}")

# %% ../../nbs/src/ets.ipynb 22
def switch_criterion(x: str) -> _ets.Criterion:
    if x == "lik":
        return _ets.Criterion.Likelihood
    if x == "mse":
        return _ets.Criterion.MSE
    if x == "amse":
        return _ets.Criterion.AMSE
    if x == "sigma":
        return _ets.Criterion.Sigma
    if x == "mae":
        return _ets.Criterion.MAE
    raise ValueError(f"Unknown crtierion {x}")

# %% ../../nbs/src/ets.ipynb 24
def pegelsresid_C(
    y: np.ndarray,
    m: int,
    init_state: np.ndarray,
    errortype: str,
    trendtype: str,
    seasontype: str,
    damped: bool,
    alpha: float,
    beta: float,
    gamma: float,
    phi: float,
    nmse: int,
):
    n = len(y)
    p = len(init_state)
    x = np.full(p * (n + 1), fill_value=np.nan)
    x[:p] = init_state
    e = np.full_like(y, fill_value=np.nan)
    if not damped:
        phi = 1.0
    if trendtype == "N":
        beta = 0.0
    if seasontype == "N":
        gamma = 0.0
    amse = np.full(nmse, fill_value=np.nan)
    lik = _ets.calc(
        x,
        e,
        amse,
        nmse,
        y,
        switch(errortype),
        switch(trendtype),
        switch(seasontype),
        alpha,
        beta,
        gamma,
        phi,
        m,
    )
    x = x.reshape((n + 1, p))
    if not np.isnan(lik):
        if np.abs(lik + 99999) < 1e-7:
            lik = np.nan
    return amse, e, x, lik

# %% ../../nbs/src/ets.ipynb 25
def optimize_ets_target_fn(
    x0,
    par,
    y,
    nstate,
    errortype,
    trendtype,
    seasontype,
    damped,
    par_noopt,
    lowerb,
    upperb,
    opt_crit,
    nmse,
    bounds,
    m,
    pnames,
    pnames2,
):
    alpha = par_noopt["alpha"] if np.isnan(par["alpha"]) else par["alpha"]
    if np.isnan(alpha):
        raise ValueError("alpha problem!")
    if trendtype != "N":
        beta = par_noopt["beta"] if np.isnan(par["beta"]) else par["beta"]
        if np.isnan(beta):
            raise ValueError("beta problem!")
    else:
        beta = np.nan
    if seasontype != "N":
        gamma = par_noopt["gamma"] if np.isnan(par["gamma"]) else par["gamma"]
        if np.isnan(gamma):
            raise ValueError("gamma problem!")
    else:
        m = 1
        gamma = np.nan
    if damped:
        phi = par_noopt["phi"] if np.isnan(par["phi"]) else par["phi"]
        if np.isnan(phi):
            raise ValueError("phi problem!")
    else:
        phi = np.nan

    optAlpha = not np.isnan(alpha)
    optBeta = not np.isnan(beta)
    optGamma = not np.isnan(gamma)
    optPhi = not np.isnan(phi)

    if not np.isnan(par_noopt["alpha"]):
        optAlpha = False
    if not np.isnan(par_noopt["beta"]):
        optBeta = False
    if not np.isnan(par_noopt["gamma"]):
        optGamma = False
    if not np.isnan(par_noopt["phi"]):
        optPhi = False

    if not damped:
        phi = 1.0
    if trendtype == "N":
        beta = 0.0
    if seasontype == "N":
        gamma = 0.0
    opt_res = _ets.optimize(
        x0,
        y,
        nstate,
        switch(errortype),
        switch(trendtype),
        switch(seasontype),
        switch_criterion(opt_crit),
        nmse,
        m,
        optAlpha,
        optBeta,
        optGamma,
        optPhi,
        alpha,
        beta,
        gamma,
        phi,
        lowerb,
        upperb,
        1e-4,
        1_000,
        True,
    )
    return results(*opt_res)

# %% ../../nbs/src/ets.ipynb 26
def etsmodel(
    y: np.ndarray,
    m: int,
    errortype: str,
    trendtype: str,
    seasontype: str,
    damped: bool,
    alpha: float,
    beta: float,
    gamma: float,
    phi: float,
    lower: np.ndarray,
    upper: np.ndarray,
    opt_crit: str,
    nmse: int,
    bounds: str,
    maxit: int = 2_000,
    control=None,
    seed=None,
    trace: bool = False,
):
    if seasontype == "N":
        m = 1
    # if not np.isnan(alpha):
    #    upper[2] = min(alpha, upper[2])
    #    upper[3] = min(1 - alpha, upper[3])
    # if not np.isnan(beta):
    #    lower[1] = max(beta, lower[1])
    #    upper[1] = min(1 - gamma, upper[1])
    par_ = initparam(
        alpha, beta, gamma, phi, trendtype, seasontype, damped, lower, upper, m, bounds
    )
    par_noopt = dict(alpha=alpha, beta=beta, gamma=gamma, phi=phi)

    if not np.isnan(par_["alpha"]):
        alpha = par_["alpha"]
    if not np.isnan(par_["beta"]):
        beta = par_["beta"]
    if not np.isnan(par_["gamma"]):
        gamma = par_["gamma"]
    if not np.isnan(par_["phi"]):
        phi = par_["phi"]
    if not check_param(alpha, beta, gamma, phi, lower, upper, bounds, m):
        raise Exception("Parameters out of range")
    # initialize state
    init_state = initstate(y, m, trendtype, seasontype)
    nstate = len(init_state)
    par_ = {key: val for key, val in par_.items() if not np.isnan(val)}
    par = np.full(len(par_) + nstate, fill_value=np.nan)
    par[: len(par_)] = list(par_.values())
    par[len(par_) :] = init_state
    lower_ = np.full_like(par, fill_value=-np.inf)
    upper_ = np.full_like(par, fill_value=np.inf)
    j = 0
    for i, pr in enumerate(["alpha", "beta", "gamma", "phi"]):
        if pr in par_.keys():
            lower_[j] = lower[i]
            upper_[j] = upper[i]
            j += 1
    lower = lower_
    upper = upper_
    np_ = len(par)
    if np_ >= len(y) - 1:
        return dict(
            aic=np.inf,
            bic=np.inf,
            aicc=np.inf,
            mse=np.inf,
            amse=np.inf,
            fit=None,
            par=par,
            states=init_state,
        )
    fred = optimize_ets_target_fn(
        x0=par,
        par=par_,
        y=y,
        nstate=nstate,
        errortype=errortype,
        trendtype=trendtype,
        seasontype=seasontype,
        damped=damped,
        par_noopt=par_noopt,
        lowerb=lower,
        upperb=upper,
        opt_crit=opt_crit,
        nmse=nmse,
        bounds=bounds,
        m=m,
        pnames=par_.keys(),
        pnames2=par_noopt.keys(),
    )
    fit_par = fred.x
    init_state = fit_par[-nstate:]
    if seasontype != "N":
        init_state = np.hstack(
            [
                init_state,
                m * (seasontype == "M")
                - init_state[(1 + (trendtype != "N")) : nstate].sum(),
            ]
        )
    j = 0
    if not np.isnan(fit_par[j]):
        alpha = fit_par[j]
        j += 1
    if trendtype != "N":
        if not np.isnan(fit_par[j]):
            beta = fit_par[j]
        j += 1
    if seasontype != "N":
        if not np.isnan(fit_par[j]):
            gamma = fit_par[j]
        j += 1
    if damped:
        if not np.isnan(fit_par[j]):
            phi = fit_par[j]

    amse, e, states, lik = pegelsresid_C(
        y,
        m,
        init_state,
        errortype,
        trendtype,
        seasontype,
        damped,
        alpha,
        beta,
        gamma,
        phi,
        nmse,
    )
    np_ = np_ + 1
    ny = len(y)
    aic = lik + 2 * np_
    bic = lik + np.log(ny) * np_
    if ny - np_ - 1 != 0.0:
        aicc = aic + 2 * np_ * (np_ + 1) / (ny - np_ - 1)
    else:
        aicc = np.inf

    mse = amse[0]
    amse = np.mean(amse)

    fit_par = np.concatenate([[alpha, beta, gamma, phi], init_state])
    if errortype == "A":
        fits = y - e
    else:
        fits = y / (1 + e)

    sigma2 = np.sum(e**2) / (ny - np_ - 1)

    return dict(
        loglik=-0.5 * lik,
        aic=aic,
        bic=bic,
        aicc=aicc,
        mse=mse,
        amse=amse,
        fit=fred,
        residuals=e,
        components=f"{errortype}{trendtype}{seasontype}{'D' if damped else 'N'}",
        m=m,
        nstate=nstate,
        fitted=fits,
        states=states,
        par=fit_par,
        sigma2=sigma2,
        n_params=np_,
    )

# %% ../../nbs/src/ets.ipynb 28
def is_constant(x):
    return np.all(x[0] == x)

# %% ../../nbs/src/ets.ipynb 30
def ets_f(
    y,
    m,
    model="ZZZ",
    damped=None,
    alpha=None,
    beta=None,
    gamma=None,
    phi=None,
    additive_only=None,
    blambda=None,
    biasadj=None,
    lower=None,
    upper=None,
    opt_crit="lik",
    nmse=3,
    bounds="both",
    ic="aicc",
    restrict=True,
    allow_multiplicative_trend=False,
    use_initial_values=False,
    maxit=2_000,
):
    y = y.astype(np.float64, copy=False)
    # converting params to floats
    # to improve numba compilation
    if alpha is None:
        alpha = np.nan
    if beta is None:
        beta = np.nan
    if gamma is None:
        gamma = np.nan
    if phi is None:
        phi = np.nan
    if blambda is not None:
        raise NotImplementedError("`blambda` not None")
    if nmse < 1 or nmse > 30:
        raise ValueError("nmse out of range")
    if lower is None:
        lower = np.array([0.0001, 0.0001, 0.0001, _PHI_LOWER])
    if upper is None:
        upper = np.array([0.9999, 0.9999, 0.9999, _PHI_UPPER])
    if any(upper < lower):
        raise ValueError("Lower limits must be less than upper limits")
    # check if y is contant
    if is_constant(y):
        return etsmodel(
            y=y,
            m=m,
            errortype="A",
            trendtype="N",
            seasontype="N",
            alpha=0.9999,
            beta=beta,
            gamma=gamma,
            phi=phi,
            damped=False,
            lower=lower,
            upper=upper,
            opt_crit=opt_crit,
            nmse=nmse,
            bounds=bounds,
            maxit=maxit,
        )

    if isinstance(model, dict):
        m = model["m"]
        errortype, trendtype, seasontype = model["components"][:3]
        damped = model["components"][3] != "N"
        alpha, beta, gamma, phi = model["par"][:4]
        init_state = model["par"][4:]
        # Recompute errors from pegelsresid.C
        amse, e, states, lik = pegelsresid_C(
            y=y,
            m=m,
            init_state=init_state,
            errortype=errortype,
            trendtype=trendtype,
            seasontype=seasontype,
            damped=damped,
            alpha=alpha,
            beta=beta,
            gamma=gamma,
            phi=phi,
            nmse=nmse,
        )
        fred = model["fit"]
        nstate = len(init_state)
        np_ = model["n_params"] - 1
        np_ = np_ + 1
        ny = len(y)
        aic = lik + 2 * np_
        bic = lik + np.log(ny) * np_
        if ny - np_ - 1 != 0.0:
            aicc = aic + 2 * np_ * (np_ + 1) / (ny - np_ - 1)
        else:
            aicc = np.inf

        mse = amse[0]
        amse = np.mean(amse)

        fit_par = np.concatenate([[alpha, beta, gamma, phi], init_state])
        if errortype == "A":
            fits = y - e
        else:
            # protect e == -1
            aux_e = np.copy(e)
            aux_e[aux_e == -1.0] = -1 + 1e-3
            fits = y / (1 + aux_e)
        sq_e = e**2

        sigma2 = sq_e[~np.isinf(sq_e)].sum() / (ny - np_ - 1)

        return dict(
            loglik=-0.5 * lik,
            aic=aic,
            bic=bic,
            aicc=aicc,
            mse=mse,
            amse=amse,
            fit=fred,
            residuals=e,
            components=f"{errortype}{trendtype}{seasontype}{'D' if damped else 'N'}",
            m=m,
            nstate=nstate,
            fitted=fits,
            states=states,
            par=fit_par,
            sigma2=sigma2,
            n_params=np_,
        )

    errortype, trendtype, seasontype = model
    if errortype not in ["M", "A", "Z"]:
        raise ValueError("Invalid error type")
    if trendtype not in ["N", "A", "M", "Z"]:
        raise ValueError("Invalid trend type")
    if seasontype not in ["N", "A", "M", "Z"]:
        raise ValueError("Invalid season type")
    if m < 1 or len(y) <= m:
        seasontype = "N"
    if m == 1:
        if seasontype == "A" or seasontype == "M":
            raise ValueError("Nonseasonal data")
        else:
            # model[3] = 'N'
            seasontype = "N"
    if restrict:
        if (
            (errortype == "A" and (trendtype == "M" or seasontype == "M"))
            or (errortype == "M" and trendtype == "M" and seasontype == "A")
            or (
                additive_only
                and (errortype == "M" or trendtype == "M" or seasontype == "M")
            )
        ):
            raise ValueError("Forbidden model combination")
    data_positive = min(y) > 0
    if (not data_positive) and errortype == "M":
        raise ValueError("Inappropriate model for data with negative or zero values")
    if damped is not None:
        if damped and trendtype == "N":
            ValueError("Forbidden model combination")
    n = len(y)
    npars = 2  # alpha + l0
    if trendtype in ["A", "M"]:
        npars += 2  # beta + b0
    if seasontype in ["A", "M"]:
        npars += 2  # gamma + s
    if damped is not None:
        npars += damped
    # ses for non-optimized tiny datasets
    if n <= npars + 4:
        # we need HoltWintersZZ function
        raise NotImplementedError("tiny datasets")
    # fit model (assuming only one nonseasonal model)
    if errortype == "Z":
        errortype = ["A", "M"]
    if trendtype == "Z":
        trendtype = ["N", "A"]
        if allow_multiplicative_trend:
            trendtype += ["M"]
    if seasontype == "Z":
        seasontype = ["N", "A", "M"]
    if damped is None:
        damped = [True, False]
    else:
        damped = [damped]
    best_ic = np.inf
    for etype in errortype:
        for ttype in trendtype:
            for stype in seasontype:
                for dtype in damped:
                    if ttype == "N" and dtype:
                        continue
                    if restrict:
                        if etype == "A" and (ttype == "M" or stype == "M"):
                            continue
                        if etype == "M" and ttype == "M" and stype == "A":
                            continue
                        if additive_only and (
                            etype == "M" or ttype == "M" or stype == "M"
                        ):
                            continue
                    if (not data_positive) and etype == "M":
                        continue
                    if (not data_positive) and stype == "M":
                        # see https://github.com/statsmodels/statsmodels/blob/46116c493697b5456e960b1dc2932264703b6c59/statsmodels/tsa/seasonal.py#L157
                        continue
                    if stype != "N" and m == 1:
                        continue
                    fit = etsmodel(
                        y,
                        m,
                        etype,
                        ttype,
                        stype,
                        dtype,
                        alpha,
                        beta,
                        gamma,
                        phi,
                        lower=lower,
                        upper=upper,
                        opt_crit=opt_crit,
                        nmse=nmse,
                        bounds=bounds,
                        maxit=maxit,
                    )
                    fit_ic = fit[ic]
                    if not np.isnan(fit_ic):
                        if fit_ic < best_ic:
                            model = fit
                            best_ic = fit_ic
                            best_e = etype
                            best_t = ttype
                            best_s = stype
                            best_d = dtype
    if np.isinf(best_ic):
        raise Exception("no model able to be fitted")
    model["method"] = f"ETS({best_e},{best_t}{'d' if best_d else ''},{best_s})"
    return model

# %% ../../nbs/src/ets.ipynb 31
def pegelsfcast_C(h, obj, npaths=None, level=None, bootstrap=None):
    forecast = np.full(h, fill_value=np.nan)
    states = obj["states"][-1, :]
    etype, ttype, stype = [switch(comp) for comp in obj["components"][:3]]
    phi = 1 if obj["components"][3] == "N" else obj["par"][3]
    m = obj["m"]
    etsforecast(x=states, m=m, trend=ttype, season=stype, phi=phi, h=h, f=forecast)
    return forecast

# %% ../../nbs/src/ets.ipynb 32
def _compute_sigmah(pf, h, sigma, cvals):
    theta = np.full(h, np.nan)
    theta[0] = pf[0] ** 2

    for k in range(1, h):
        sum_val = cvals[:k] ** 2 @ theta[:k][::-1]
        theta[k] = pf[k] ** 2 + sigma * sum_val

    return (1 + sigma) * theta - pf**2

# %% ../../nbs/src/ets.ipynb 33
def _class3models(
    h,
    sigma,
    last_state,
    season_length,
    error,
    trend,
    seasonality,
    damped,
    alpha,
    beta,
    gamma,
    phi,
):

    if damped == "N":
        damped_val = False
    else:
        damped_val = True

    p = len(last_state)

    if trend != "N":
        H1 = np.array([[1, 1]])
    else:
        H1 = np.array([[1]])

    H2 = np.concatenate((np.zeros(season_length - 1), np.array([1]))).reshape(
        1, season_length
    )

    if trend == "N":
        F1 = 1
        G1 = alpha
    else:
        f1 = 1
        if damped_val:
            f1 = phi
        F1 = np.array([[1, 1], [0, f1]])
        G1 = np.array([[alpha, alpha], [beta, beta]])

    f2_top = np.concatenate((np.zeros(season_length - 1), np.array([1]))).reshape(
        1, season_length
    )
    f2_bottom = np.c_[
        (
            np.identity(season_length - 1),
            np.zeros(season_length - 1).reshape(season_length - 1, 1),
        )
    ]
    F2 = np.r_[f2_top, f2_bottom]

    G2 = np.zeros((season_length, season_length))
    G2[0, season_length - 1] = gamma
    Mh = np.matmul(
        last_state[0 : (p - season_length)].reshape(
            last_state[0 : (p - season_length)].shape[0], 1
        ),
        last_state[(p - season_length) : p].reshape(1, season_length),
    )
    Vh = np.zeros((Mh.shape[0] * Mh.shape[1], Mh.shape[0] * Mh.shape[1]))
    H21 = np.kron(H2, H1)
    F21 = np.kron(F2, F1)
    G21 = np.kron(G2, G1)
    K = np.kron(G2, F1) + np.kron(F2, G1)
    mu = np.zeros(h)
    var = np.zeros(h)

    for i in range(0, h):
        mu[i] = (H1 @ (Mh @ H2.T)).item()
        var[i] = (1 + sigma) * (H21 @ (Vh @ H21.T)).item() + sigma * mu[i] ** 2
        vecMh = Mh.flatten()
        exp1 = np.matmul(F21, np.matmul(Vh, np.transpose(F21)))
        exp2 = np.matmul(F21, np.matmul(Vh, np.transpose(G21)))
        exp3 = np.matmul(G21, np.matmul(Vh, np.transpose(F21)))
        exp4 = np.matmul(
            K,
            np.matmul(Vh + (vecMh * vecMh.reshape(vecMh.shape[0], 1)), np.transpose(K)),
        )
        exp5 = np.matmul(
            sigma * G21,
            np.matmul(
                3 * Vh + 2 * vecMh * vecMh.reshape(vecMh.shape[0], 1), np.transpose(G21)
            ),
        )
        Vh = exp1 + sigma * (exp2 + exp3 + exp4 + exp5)

    if trend == "N":
        Mh = (
            F1 * np.matmul(Mh, np.transpose(F2))
            + G1 * np.matmul(Mh, np.transpose(G2)) * sigma
        )
    else:
        Mh = (
            np.matmul(F1, np.matmul(Mh, np.transpose(F2)))
            + np.matmul(G1, np.matmul(Mh, np.transpose(G2))) * sigma
        )

    return var

# %% ../../nbs/src/ets.ipynb 34
def _compute_pred_intervals(model, forecasts, h, level):
    sigma = model["sigma2"]
    season_length = model["m"]
    pf = forecasts["mean"]

    model_type = model["components"]
    steps = steps = np.arange(1, h + 1)
    hm = np.floor((h - 1) / season_length)
    last_state = model["states"][-1]

    # error, trend, and seasonality type
    error = model_type[0]
    trend = model_type[1]
    seasonality = model_type[2]
    damped = model_type[3]

    # parameters
    alpha = model["par"][0]
    beta = model["par"][1]
    gamma = model["par"][2]
    phi = model["par"][3]

    exp1 = alpha**2 + alpha * beta * steps + (1 / 6) * beta**2 * steps * (2 * steps - 1)
    exp2 = (beta * phi * steps) / (1 - phi) ** 2
    exp3 = 2 * alpha * (1 - phi) + beta * phi
    exp4 = (beta * phi * (1 - phi**steps)) / ((1 - phi) ** 2 * (1 - phi**2))
    exp5 = 2 * alpha * (1 - phi**2) + beta * phi * (1 + 2 * phi - phi**steps)

    compute_intervals = True
    # Class 1 models
    if error == "A" and trend == "N" and seasonality == "N" and damped == "N":
        # Model ANN
        sigmah = 1 + alpha**2 * (steps - 1)
        sigmah = sigma * sigmah

    elif error == "A" and trend == "A" and seasonality == "N" and damped == "N":
        # Model AAN
        sigmah = 1 + (steps - 1) * exp1
        sigmah = sigma * sigmah

    elif error == "A" and trend == "A" and seasonality == "N" and damped == "D":
        # Model AAdN
        sigmah = 1 + alpha**2 * (steps - 1) + exp2 * exp3 - exp4 * exp5
        sigmah = sigma * sigmah

    elif error == "A" and trend == "N" and seasonality == "A" and damped == "N":
        # Model ANA
        sigmah = 1 + alpha**2 * (steps - 1) + gamma * hm * (2 * alpha + gamma)
        sigmah = sigma * sigmah

    elif error == "A" and trend == "A" and seasonality == "A" and damped == "N":
        # Model AAA
        exp6 = 2 * alpha + gamma + beta * season_length * (hm + 1)
        sigmah = 1 + (steps - 1) * exp1 + gamma * hm * exp6
        sigmah = sigma * sigmah

    elif error == "A" and trend == "A" and seasonality == "A" and damped == "D":
        # Model AAdA
        exp7 = (2 * beta * gamma * phi) / ((1 - phi) * (1 - phi**season_length))
        exp8 = hm * (1 - phi**season_length) - phi**season_length * (
            1 - phi ** (season_length * hm)
        )
        sigmah = (
            1
            + alpha**2 * (steps - 1)
            + exp2 * exp3
            - exp4 * exp5
            + gamma * hm * (2 * alpha + gamma)
            + exp7 * exp8
        )
        sigmah = sigma * sigmah

    # Class 2 models
    elif error == "M" and trend == "N" and seasonality == "N" and damped == "N":
        # Model MNN
        cvals = np.full(h, alpha)
        sigmah = _compute_sigmah(pf, h, sigma, cvals)

    elif error == "M" and trend == "A" and seasonality == "N" and damped == "N":
        # Model MAN
        cvals = alpha + beta * steps
        sigmah = _compute_sigmah(pf, h, sigma, cvals)

    elif error == "M" and trend == "A" and seasonality == "N" and damped == "D":
        # Model MAdN
        cvals = np.full(h, np.nan)
        for k in range(1, h + 1):
            sum_phi = 0
            for j in range(1, k + 1):
                sum_phi = sum_phi + phi**j
            cvals[k - 1] = alpha + beta * sum_phi
        sigmah = _compute_sigmah(pf, h, sigma, cvals)

    elif error == "M" and trend == "N" and seasonality == "A" and damped == "N":
        # Model MNA
        dvals = np.zeros(h)
        for k in range(1, h + 1):
            val = k % season_length
            if val == 0:
                dvals[k - 1] = 1
        cvals = alpha + gamma * dvals
        sigmah = _compute_sigmah(pf, h, sigma, cvals)

    elif error == "M" and trend == "A" and seasonality == "A" and damped == "N":
        # Model MAA
        dvals = np.zeros(h)
        for k in range(1, h + 1):
            val = k % season_length
            if val == 0:
                dvals[k - 1] = 1
        cvals = alpha * beta * steps + gamma * dvals
        sigmah = _compute_sigmah(pf, h, sigma, cvals)

    elif error == "M" and trend == "A" and seasonality == "A" and damped == "D":
        # Model MAdA
        dvals = np.zeros(h)
        for k in range(1, h + 1):
            val = k % season_length
            if val == 0:
                dvals[k - 1] = 1
        cvals = np.full(h, np.nan)
        for k in range(1, h + 1):
            sum_phi = 0
            for j in range(1, k + 1):
                sum_phi = sum_phi + phi**j
            cvals[k - 1] = alpha + beta * sum_phi + gamma * dvals[k - 1]
        sigmah = _compute_sigmah(pf, h, sigma, cvals)

    elif error == "M" and seasonality == "M":
        # Class 3 models
        sigmah = _class3models(
            h,
            sigma,
            last_state,
            season_length,
            error,
            trend,
            seasonality,
            damped,
            alpha,
            beta,
            gamma,
            phi,
        )

    else:
        # Classes 4 and 5 models
        np.random.seed(1)
        compute_intervals = False
        nsim = 5000
        y_path = np.zeros([nsim, h])

        if math.isnan(beta):
            beta = 0
        if math.isnan(gamma):
            gamma = 0
        if math.isnan(phi):
            phi = 0

        for k in range(nsim):
            e = np.random.normal(0, np.sqrt(sigma), h)
            yhat = np.zeros(h)
            etssimulate(
                last_state,
                season_length,
                switch(error),
                switch(trend),
                switch(seasonality),
                alpha,
                beta,
                gamma,
                phi,
                h,
                yhat,
                e,
            )
            y_path[k,] = yhat

        lower = np.quantile(y_path, 0.5 - np.array(level) / 200, axis=0)
        upper = np.quantile(y_path, 0.5 + np.array(level) / 200, axis=0)
        pi = {
            **{f"lo-{lv}": lower[i] for i, lv in enumerate(level)},
            **{f"hi-{lv}": upper[i] for i, lv in enumerate(level)},
        }

    if compute_intervals:
        pi = _calculate_intervals(forecasts, level=level, h=h, sigmah=np.sqrt(sigmah))

    return pi

# %% ../../nbs/src/ets.ipynb 35
def forecast_ets(obj, h, level=None):
    fcst = pegelsfcast_C(h, obj)
    out = {"mean": fcst}
    out["residuals"] = obj["residuals"]
    out["fitted"] = obj["fitted"]
    if level is not None:
        pi = _compute_pred_intervals(model=obj, forecasts=out, level=level, h=h)
        out = {**out, **pi}
    return out

# %% ../../nbs/src/ets.ipynb 42
def forward_ets(fitted_model, y):
    return ets_f(y=y, m=fitted_model["m"], model=fitted_model)
