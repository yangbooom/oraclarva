"""Minimal CMA-ES (Hansen 2016 tutorial, rank-mu + rank-one update), numpy only.

Black-box: works with the non-differentiable whole-brain simulator.  The caller
asks for a population, evaluates it however it likes (e.g. in parallel), and
reports the losses back.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class CMAES:
    mean: np.ndarray
    sigma: float
    popsize: int | None = None
    seed: int = 0
    rng: np.random.Generator = field(init=False)

    def __post_init__(self) -> None:
        self.mean = np.asarray(self.mean, dtype=float)
        n = self.n = self.mean.size
        self.rng = np.random.default_rng(self.seed)
        self.lam = self.popsize or 4 + int(3 * np.log(n))
        self.mu = self.lam // 2
        w = np.log(self.mu + 0.5) - np.log(np.arange(1, self.mu + 1))
        self.weights = w / w.sum()
        self.mueff = 1.0 / np.sum(self.weights**2)
        self.cc = (4 + self.mueff / n) / (n + 4 + 2 * self.mueff / n)
        self.cs = (self.mueff + 2) / (n + self.mueff + 5)
        self.c1 = 2 / ((n + 1.3) ** 2 + self.mueff)
        self.cmu = min(1 - self.c1, 2 * (self.mueff - 2 + 1 / self.mueff) / ((n + 2) ** 2 + self.mueff))
        self.damps = 1 + 2 * max(0.0, np.sqrt((self.mueff - 1) / (n + 1)) - 1) + self.cs
        self.chin = np.sqrt(n) * (1 - 1 / (4 * n) + 1 / (21 * n**2))
        self.pc = np.zeros(n)
        self.ps = np.zeros(n)
        self.C = np.eye(n)
        self.generation = 0
        self.best_x: np.ndarray | None = None
        self.best_f = np.inf

    def ask(self) -> np.ndarray:
        eigvals, B = np.linalg.eigh(self.C)
        self._B, self._D = B, np.sqrt(np.maximum(eigvals, 1e-20))
        z = self.rng.standard_normal((self.lam, self.n))
        self._y = z @ (B * self._D).T
        return self.mean + self.sigma * self._y

    def tell(self, xs: np.ndarray, losses: np.ndarray) -> None:
        losses = np.asarray(losses, dtype=float)
        order = np.argsort(losses)
        if losses[order[0]] < self.best_f:
            self.best_f, self.best_x = float(losses[order[0]]), np.array(xs[order[0]])
        y = self._y[order[: self.mu]]
        y_w = self.weights @ y
        self.mean = self.mean + self.sigma * y_w
        invsqrt = self._B @ np.diag(1 / self._D) @ self._B.T
        self.ps = (1 - self.cs) * self.ps + np.sqrt(self.cs * (2 - self.cs) * self.mueff) * (invsqrt @ y_w)
        self.generation += 1
        hsig = np.linalg.norm(self.ps) / np.sqrt(1 - (1 - self.cs) ** (2 * self.generation)) / self.chin < 1.4 + 2 / (self.n + 1)
        self.pc = (1 - self.cc) * self.pc + hsig * np.sqrt(self.cc * (2 - self.cc) * self.mueff) * y_w
        rank_mu = (y.T * self.weights) @ y
        self.C = (
            (1 - self.c1 - self.cmu) * self.C
            + self.c1 * (np.outer(self.pc, self.pc) + (1 - hsig) * self.cc * (2 - self.cc) * self.C)
            + self.cmu * rank_mu
        )
        self.C = (self.C + self.C.T) / 2
        self.sigma *= np.exp((self.cs / self.damps) * (np.linalg.norm(self.ps) / self.chin - 1))
