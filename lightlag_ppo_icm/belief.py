"""Where the rover probably is: a four-number Kalman filter built from the published noise.

The state is the position (x, y) and one complex gain g = gr + i*gi that turns a drive as
commanded into the drive as driven: |g| is a scale (wheels of a hidden size, slip away from the
middle of its published range) and its angle a rotation (the hidden heading bias). A drive
whose expected displacement is d moves the rover by g * d, which is linear in the state, so
the filter is exact for this model:

    x' = x + gr*dx - gi*dy          F = [[1, 0, dx, -dy],
    y' = y + gr*dy + gi*dx               [0, 1, dy,  dx],
                                         [0, 0,  1,   0],
                                         [0, 0,  0,   1]]

Position fixes correct the position and, through the cross terms, the gain; visual odometry
reads the scale and a sun compass the rotation, when the telemetry carries them. This is a
deliberately plain estimator: it is the fixed part of the baseline, the policy is the learned
part. The scripted players of the max env use a particle filter that fuses far more.
"""

import numpy as np


class Belief:
    def __init__(self, x, y, var_scale, var_rot):
        self.m = np.array([float(x), float(y), 1.0, 0.0])
        self.P = np.diag([0.0, 0.0, float(var_scale), float(var_rot)])

    def copy(self):
        other = Belief.__new__(Belief)
        other.m, other.P = self.m.copy(), self.P.copy()
        return other

    @property
    def sigma(self):
        """Standard deviation of the position, per axis."""
        return float(np.sqrt(max(0.0, 0.5 * (self.P[0, 0] + self.P[1, 1]))))

    def move(self, dx, dy, q_pos, q_scale, q_rot):
        """A drive whose expected displacement is (dx, dy), with the noise it adds."""
        gr, gi = self.m[2], self.m[3]
        self.m[0] += gr * dx - gi * dy
        self.m[1] += gr * dy + gi * dx
        f = np.eye(4)
        f[0, 2], f[0, 3], f[1, 2], f[1, 3] = dx, -dy, dy, dx
        p = f @ self.P @ f.T
        p[0, 0] += q_pos
        p[1, 1] += q_pos
        p[2, 2] += q_scale
        p[3, 3] += q_rot
        self.P = p

    def fix(self, zx, zy, var, gate=None):
        """A position fix with variance `var` per axis. False when the gate rejects it as an outlier."""
        s = self.P[:2, :2] + var * np.eye(2)
        det = s[0, 0] * s[1, 1] - s[0, 1] * s[1, 0]
        if det <= 0:
            return False
        s_inv = np.array([[s[1, 1], -s[0, 1]], [-s[1, 0], s[0, 0]]]) / det
        nu = np.array([zx - self.m[0], zy - self.m[1]])
        if gate is not None and float(nu @ s_inv @ nu) > gate:
            return False
        k = self.P[:, :2] @ s_inv
        self.m = self.m + k @ nu
        self._shrink(self.P - k @ self.P[:2, :])
        return True

    def reading(self, index, z, var):
        """A direct reading of one state number: 2 the scale, 3 the rotation in radians."""
        k = self.P[:, index] / (self.P[index, index] + var)
        self.m = self.m + k * (z - self.m[index])
        self._shrink(self.P - np.outer(k, self.P[index, :]))

    def _shrink(self, p):
        self.P = 0.5 * (p + p.T)
        self.m[2] = min(1.6, max(0.5, self.m[2]))
        self.m[3] = min(0.6, max(-0.6, self.m[3]))
