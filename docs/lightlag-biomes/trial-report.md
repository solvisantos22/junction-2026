# Biome trial

52080 episode rows; profiles rush, rush_noisy; delays 0, 3, 5; seeds 2000-2039 (40).
Share = score / maximum available. Home = alive at base at the horizon. Scripted controllers only; bounds use privileged information and are not ranked.

## Best controller in each biome

| Biome | Best controller | Share | Home | `kf_mpc` (1) | 24 | `blind` | `cautious` | Bound 16 |
|---|---|---|---|---|---|---|---|---|
| Main Mars | 20 (cubature filter + aim at disc + turn-cost budget + window awareness) | 78.7% | 100% | 77.3% | 78.7% | 59.4% | 46.0% | 83.3% |
| Relay Pass Schedule | 20 (cubature filter + aim at disc + turn-cost budget + window awareness) | 74.2% | 100% | 69.0% | 74.1% | 59.4% | 44.8% | 75.5% |
| Hidden Valley | 33 (31 plus the executive (as 32)) | 77.4% | 99% | 74.5% | 75.6% | 57.2% | 44.0% | 79.6% |
| Bagnold Dunes | 34 (27 with the guarded moves armed only when a probe is free: one telemet…) | 76.4% | 100% | 74.4% | 76.0% | 55.1% | 45.5% | 78.8% |
| Troy Crust | 26 (24 + Bayesian unmapped-sand belief (Beta prior in metres) priced on ev…) | 72.3% | 100% | 71.2% | 71.8% | 53.0% | 42.7% | 77.8% |
| Gale Rock Field | 34 (27 with the guarded moves armed only when a probe is free: one telemet…) | 72.3% | 100% | 70.9% | 72.0% | 43.8% | 42.5% | 77.3% |
| Meridiani Ripple Plains | 10 (particle filter whose slips random-walk (can follow a slip change)) | 74.3% | 100% | 73.8% | 74.1% | 56.7% | 28.8% | 82.2% |

## Overall: mean share with every biome weighted equally

| Rank | Controller | All biomes | New biomes only | Main Mars | Relay Pass Schedule | Hidden Valley | Bagnold Dunes | Troy Crust | Gale Rock Field | Meridiani Ripple Plains |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 33 (31 plus the executive (as 32)) | 74.9% | 74.2% | 78.7% | 74.1% | 77.4% | 76.0% | 71.8% | 72.0% | 74.1% |
| 2 | 31 (24 plus the slip-check-aware layer (as 30)) | 74.8% | 74.1% | 78.7% | 74.1% | 76.7% | 76.0% | 71.8% | 72.0% | 74.1% |
| 3 | 34 (27 with the guarded moves armed only when a probe is free: one telemet…) | 74.7% | 74.1% | 78.6% | 74.1% | 75.4% | 76.4% | 72.1% | 72.3% | 74.1% |
| 4 | 26 (24 + Bayesian unmapped-sand belief (Beta prior in metres) priced on ev…) | 74.7% | 74.0% | 78.6% | 74.1% | 75.4% | 76.0% | 72.3% | 72.1% | 74.0% |
| 5 | 22 (19 + battery sand odometer: unmapped sand read off the battery is adde…) | 74.6% | 73.9% | 78.7% | 74.1% | 75.6% | 76.0% | 71.8% | 72.0% | 74.1% |
| 6 | 24 (19 + battery sand odometer (22) + stay-alive rule (23)) | 74.6% | 73.9% | 78.7% | 74.1% | 75.6% | 76.0% | 71.8% | 72.0% | 74.1% |
| 7 | 25 (24 + map doubt: once the map is shown wrong, undriven bedrock on the w…) | 74.6% | 73.9% | 78.7% | 74.1% | 75.6% | 76.0% | 71.7% | 72.0% | 74.1% |
| 8 | 19 (controller 1 + aim at disc + turn-cost budget + window awareness) | 74.6% | 73.9% | 78.7% | 74.1% | 75.6% | 76.0% | 71.6% | 72.0% | 74.1% |
| 9 | 23 (19 + stay-alive rule: never send a command expected to empty the batte…) | 74.6% | 73.9% | 78.7% | 74.1% | 75.6% | 76.0% | 71.6% | 72.0% | 74.1% |
| 10 | 20 (cubature filter + aim at disc + turn-cost budget + window awareness) | 74.5% | 73.8% | 78.7% | 74.2% | 75.6% | 76.0% | 71.2% | 72.0% | 73.7% |
| 11 | 18 (controller 1 aiming at the target disc instead of its centre) | 74.1% | 73.4% | 78.7% | 70.8% | 75.6% | 76.0% | 71.6% | 72.0% | 74.1% |
| 12 | 21 (particle filter + aim at disc + turn-cost budget + window awareness) | 74.1% | 73.3% | 78.7% | 74.1% | 75.3% | 74.9% | 69.3% | 72.2% | 74.2% |
| 13 | 13 (controller 1, aware of uplink windows) | 73.5% | 72.9% | 77.3% | 72.4% | 74.5% | 74.4% | 71.2% | 70.9% | 73.8% |
| 14 | 28 (27 + 26's Bayesian unmapped-sand pricing on the way home) | 73.3% | 72.6% | 77.0% | 72.6% | 73.9% | 75.2% | 70.9% | 70.5% | 72.7% |
| 15 | 32 (30 plus an executive: explicit modes switched by telemetry events (nom…) | 73.3% | 72.6% | 77.3% | 69.0% | 76.2% | 74.4% | 71.2% | 70.9% | 73.8% |
| 16 | 27 (24 + sand-aware filter propagation + adaptive fading + guarded moves) | 73.2% | 72.5% | 77.0% | 72.5% | 74.0% | 74.9% | 70.7% | 70.2% | 72.8% |
| 17 | 30 (1 plus the slip-check-aware layer: a Bayesian trip chance per terrain…) | 73.2% | 72.5% | 77.3% | 69.0% | 75.5% | 74.4% | 71.2% | 70.9% | 73.8% |
| 18 | 11 (controller 1 + process noise on slip (forgetting)) | 73.1% | 72.4% | 77.5% | 69.0% | 74.2% | 74.4% | 71.8% | 70.8% | 74.0% |
| 19 | 8 (cubature Kalman filter: sigma points through the drive kinematics + th…) | 73.1% | 72.4% | 77.4% | 69.0% | 74.5% | 74.4% | 71.5% | 71.0% | 73.7% |
| 20 | 1 (the repo's kf_mpc: EKF + delay compensation + MPC with chance constrai…) | 73.0% | 72.3% | 77.3% | 69.0% | 74.5% | 74.4% | 71.2% | 70.9% | 73.8% |
| 21 | 29 (controller 1 for the real-time clock: measures its own lag (median of…) | 73.0% | 72.3% | 77.3% | 69.0% | 74.5% | 74.4% | 71.2% | 70.9% | 73.8% |
| 22 | 14 (controller 1, budgets turn energy) | 73.0% | 72.3% | 77.3% | 69.0% | 74.5% | 74.4% | 71.2% | 70.9% | 73.8% |
| 23 | 15 (controller 1, terrain-dependent odometry noise) | 73.0% | 72.3% | 77.3% | 69.0% | 74.5% | 74.4% | 71.2% | 70.9% | 73.6% |
| 24 | 12 (iterated extended Kalman smoother: history relinearised at smoothed st…) | 72.9% | 72.2% | 77.3% | 69.0% | 74.5% | 74.3% | 70.9% | 70.9% | 73.5% |
| 25 | 10 (particle filter whose slips random-walk (can follow a slip change)) | 72.8% | 72.0% | 77.5% | 69.1% | 74.3% | 73.7% | 69.4% | 71.4% | 74.3% |
| 26 | 2 (bootstrap particle filter (500 particles) + the same planner) | 72.7% | 71.9% | 77.5% | 69.1% | 74.4% | 73.6% | 69.0% | 71.3% | 74.1% |
| 27 | `blind` | 55.0% | 54.2% | 59.4% | 59.4% | 57.2% | 55.1% | 53.0% | 43.8% | 56.7% |
| 28 | `cautious` | 42.0% | 41.4% | 46.0% | 44.8% | 44.0% | 45.5% | 42.7% | 42.5% | 28.8% |
| 29 | `solvi_reference` | 41.0% | 40.5% | 43.8% | 37.6% | 42.3% | 43.7% | 41.9% | 40.7% | 37.0% |
| 30 | `kristjan_reference` | 41.0% | 40.3% | 44.8% | 43.9% | 43.2% | 43.7% | 41.1% | 41.2% | 28.8% |

## By biome and profile: share of maximum (home and alive out of N)

### Main Mars / rush

| Controller | Delay 0 | Delay 3 | Delay 5 |
|---|---|---|---|
| 20 (cubature filter + aim at disc + turn-cost budget + window awareness) | 91% (40/40) | 85% (40/40) | 74% (40/40) |
| 21 (particle filter + aim at disc + turn-cost budget + window awareness) | 91% (40/40) | 85% (40/40) | 74% (40/40) |
| 18 (controller 1 aiming at the target disc instead of its centre) | 91% (40/40) | 85% (40/40) | 74% (40/40) |
| 19 (controller 1 + aim at disc + turn-cost budget + window awareness) | 91% (40/40) | 85% (40/40) | 74% (40/40) |
| 33 (31 plus the executive (as 32)) | 91% (40/40) | 85% (40/40) | 74% (40/40) |
| 22 (19 + battery sand odometer: unmapped sand read off the battery is adde…) | 91% (40/40) | 85% (40/40) | 74% (40/40) |
| 25 (24 + map doubt: once the map is shown wrong, undriven bedrock on the w…) | 91% (40/40) | 85% (40/40) | 74% (40/40) |
| 24 (19 + battery sand odometer (22) + stay-alive rule (23)) | 91% (40/40) | 85% (40/40) | 74% (40/40) |
| 31 (24 plus the slip-check-aware layer (as 30)) | 91% (40/40) | 85% (40/40) | 74% (40/40) |
| 23 (19 + stay-alive rule: never send a command expected to empty the batte…) | 91% (40/40) | 85% (40/40) | 74% (40/40) |
| 26 (24 + Bayesian unmapped-sand belief (Beta prior in metres) priced on ev…) | 91% (40/40) | 85% (40/40) | 75% (40/40) |
| 34 (27 with the guarded moves armed only when a probe is free: one telemet…) | 91% (40/40) | 85% (40/40) | 74% (40/40) |
| 11 (controller 1 + process noise on slip (forgetting)) | 87% (40/40) | 83% (40/40) | 73% (40/40) |
| 10 (particle filter whose slips random-walk (can follow a slip change)) | 87% (40/40) | 82% (40/40) | 73% (40/40) |
| 2 (bootstrap particle filter (500 particles) + the same planner) | 87% (40/40) | 82% (40/40) | 73% (40/40) |
| 8 (cubature Kalman filter: sigma points through the drive kinematics + th…) | 87% (40/40) | 82% (40/40) | 73% (40/40) |
| 1 (the repo's kf_mpc: EKF + delay compensation + MPC with chance constrai…) | 87% (40/40) | 82% (40/40) | 73% (40/40) |
| 32 (30 plus an executive: explicit modes switched by telemetry events (nom…) | 87% (40/40) | 82% (40/40) | 73% (40/40) |
| 29 (controller 1 for the real-time clock: measures its own lag (median of…) | 87% (40/40) | 82% (40/40) | 73% (40/40) |
| 30 (1 plus the slip-check-aware layer: a Bayesian trip chance per terrain…) | 87% (40/40) | 82% (40/40) | 73% (40/40) |
| 15 (controller 1, terrain-dependent odometry noise) | 87% (40/40) | 82% (40/40) | 73% (40/40) |
| 14 (controller 1, budgets turn energy) | 87% (40/40) | 82% (40/40) | 73% (40/40) |
| 13 (controller 1, aware of uplink windows) | 87% (40/40) | 82% (40/40) | 73% (40/40) |
| 12 (iterated extended Kalman smoother: history relinearised at smoothed st…) | 87% (40/40) | 82% (40/40) | 73% (40/40) |
| 28 (27 + 26's Bayesian unmapped-sand pricing on the way home) | 90% (40/40) | 81% (40/40) | 73% (40/40) |
| 27 (24 + sand-aware filter propagation + adaptive fading + guarded moves) | 90% (40/40) | 81% (40/40) | 72% (40/40) |
| `blind` | 62% (40/40) | 62% (40/40) | 62% (40/40) |
| `cautious` | 87% (40/40) | 61% (40/40) | 41% (40/40) |
| `kristjan_reference` | 70% (40/40) | 61% (40/40) | 48% (40/40) |
| `solvi_reference` | 69% (40/40) | 49% (40/40) | 34% (40/40) |
| 16 (bound: true parameters, exact telemetry, real delay, reserve 0.5, aims…) | 93% (40/40) | 86% (40/40) | 75% (40/40) |

### Main Mars / rush_noisy

| Controller | Delay 0 | Delay 3 | Delay 5 |
|---|---|---|---|
| 20 (cubature filter + aim at disc + turn-cost budget + window awareness) | 87% (40/40) | 73% (40/40) | 62% (40/40) |
| 21 (particle filter + aim at disc + turn-cost budget + window awareness) | 88% (40/40) | 73% (40/40) | 62% (40/40) |
| 18 (controller 1 aiming at the target disc instead of its centre) | 87% (40/40) | 73% (40/40) | 62% (40/40) |
| 19 (controller 1 + aim at disc + turn-cost budget + window awareness) | 87% (40/40) | 73% (40/40) | 62% (40/40) |
| 33 (31 plus the executive (as 32)) | 87% (40/40) | 73% (40/40) | 62% (40/40) |
| 22 (19 + battery sand odometer: unmapped sand read off the battery is adde…) | 87% (40/40) | 73% (40/40) | 62% (40/40) |
| 25 (24 + map doubt: once the map is shown wrong, undriven bedrock on the w…) | 87% (40/40) | 73% (40/40) | 62% (40/40) |
| 24 (19 + battery sand odometer (22) + stay-alive rule (23)) | 87% (40/40) | 73% (40/40) | 62% (40/40) |
| 31 (24 plus the slip-check-aware layer (as 30)) | 87% (40/40) | 73% (40/40) | 62% (40/40) |
| 23 (19 + stay-alive rule: never send a command expected to empty the batte…) | 87% (40/40) | 73% (40/40) | 62% (40/40) |
| 26 (24 + Bayesian unmapped-sand belief (Beta prior in metres) priced on ev…) | 87% (40/40) | 73% (40/40) | 62% (40/40) |
| 34 (27 with the guarded moves armed only when a probe is free: one telemet…) | 87% (40/40) | 73% (40/40) | 62% (40/40) |
| 11 (controller 1 + process noise on slip (forgetting)) | 88% (40/40) | 72% (40/40) | 61% (40/40) |
| 10 (particle filter whose slips random-walk (can follow a slip change)) | 88% (40/40) | 73% (40/40) | 61% (40/40) |
| 2 (bootstrap particle filter (500 particles) + the same planner) | 88% (40/40) | 73% (40/40) | 61% (40/40) |
| 8 (cubature Kalman filter: sigma points through the drive kinematics + th…) | 88% (40/40) | 73% (40/40) | 61% (40/40) |
| 1 (the repo's kf_mpc: EKF + delay compensation + MPC with chance constrai…) | 87% (40/40) | 73% (40/40) | 61% (40/40) |
| 32 (30 plus an executive: explicit modes switched by telemetry events (nom…) | 87% (40/40) | 73% (40/40) | 61% (40/40) |
| 29 (controller 1 for the real-time clock: measures its own lag (median of…) | 87% (40/40) | 73% (40/40) | 61% (40/40) |
| 30 (1 plus the slip-check-aware layer: a Bayesian trip chance per terrain…) | 87% (40/40) | 73% (40/40) | 61% (40/40) |
| 15 (controller 1, terrain-dependent odometry noise) | 87% (40/40) | 73% (40/40) | 61% (40/40) |
| 14 (controller 1, budgets turn energy) | 87% (40/40) | 73% (40/40) | 61% (40/40) |
| 13 (controller 1, aware of uplink windows) | 87% (40/40) | 73% (40/40) | 61% (40/40) |
| 12 (iterated extended Kalman smoother: history relinearised at smoothed st…) | 87% (40/40) | 73% (40/40) | 61% (40/40) |
| 28 (27 + 26's Bayesian unmapped-sand pricing on the way home) | 86% (40/40) | 72% (40/40) | 60% (40/40) |
| 27 (24 + sand-aware filter propagation + adaptive fading + guarded moves) | 87% (40/40) | 71% (40/40) | 60% (40/40) |
| `blind` | 56% (37/40) | 56% (38/40) | 58% (37/40) |
| `cautious` | 20% (9/40) | 40% (24/40) | 27% (26/40) |
| `kristjan_reference` | 41% (23/40) | 22% (19/40) | 27% (25/40) |
| `solvi_reference` | 52% (38/40) | 35% (35/40) | 24% (28/40) |
| 16 (bound: true parameters, exact telemetry, real delay, reserve 0.5, aims…) | 90% (40/40) | 84% (40/40) | 73% (40/40) |

### Relay Pass Schedule / rush

| Controller | Delay 0 | Delay 3 | Delay 5 |
|---|---|---|---|
| 20 (cubature filter + aim at disc + turn-cost budget + window awareness) | 89% (40/40) | 77% (40/40) | 68% (40/40) |
| 26 (24 + Bayesian unmapped-sand belief (Beta prior in metres) priced on ev…) | 88% (40/40) | 77% (40/40) | 68% (40/40) |
| 19 (controller 1 + aim at disc + turn-cost budget + window awareness) | 88% (40/40) | 77% (40/40) | 68% (40/40) |
| 33 (31 plus the executive (as 32)) | 88% (40/40) | 77% (40/40) | 68% (40/40) |
| 22 (19 + battery sand odometer: unmapped sand read off the battery is adde…) | 88% (40/40) | 77% (40/40) | 68% (40/40) |
| 25 (24 + map doubt: once the map is shown wrong, undriven bedrock on the w…) | 88% (40/40) | 77% (40/40) | 68% (40/40) |
| 24 (19 + battery sand odometer (22) + stay-alive rule (23)) | 88% (40/40) | 77% (40/40) | 68% (40/40) |
| 31 (24 plus the slip-check-aware layer (as 30)) | 88% (40/40) | 77% (40/40) | 68% (40/40) |
| 23 (19 + stay-alive rule: never send a command expected to empty the batte…) | 88% (40/40) | 77% (40/40) | 68% (40/40) |
| 21 (particle filter + aim at disc + turn-cost budget + window awareness) | 89% (40/40) | 77% (40/40) | 68% (40/40) |
| 34 (27 with the guarded moves armed only when a probe is free: one telemet…) | 89% (40/40) | 76% (40/40) | 68% (40/40) |
| 28 (27 + 26's Bayesian unmapped-sand pricing on the way home) | 87% (40/40) | 74% (40/40) | 66% (40/40) |
| 27 (24 + sand-aware filter propagation + adaptive fading + guarded moves) | 87% (40/40) | 74% (40/40) | 65% (40/40) |
| 13 (controller 1, aware of uplink windows) | 85% (40/40) | 74% (40/40) | 66% (40/40) |
| 18 (controller 1 aiming at the target disc instead of its centre) | 86% (40/40) | 75% (40/40) | 66% (40/40) |
| 10 (particle filter whose slips random-walk (can follow a slip change)) | 80% (40/40) | 71% (40/40) | 64% (40/40) |
| 2 (bootstrap particle filter (500 particles) + the same planner) | 80% (40/40) | 71% (40/40) | 64% (40/40) |
| 8 (cubature Kalman filter: sigma points through the drive kinematics + th…) | 80% (40/40) | 71% (40/40) | 64% (40/40) |
| 1 (the repo's kf_mpc: EKF + delay compensation + MPC with chance constrai…) | 80% (40/40) | 71% (40/40) | 64% (40/40) |
| 32 (30 plus an executive: explicit modes switched by telemetry events (nom…) | 80% (40/40) | 71% (40/40) | 64% (40/40) |
| 29 (controller 1 for the real-time clock: measures its own lag (median of…) | 80% (40/40) | 71% (40/40) | 64% (40/40) |
| 30 (1 plus the slip-check-aware layer: a Bayesian trip chance per terrain…) | 80% (40/40) | 71% (40/40) | 64% (40/40) |
| 15 (controller 1, terrain-dependent odometry noise) | 80% (40/40) | 71% (40/40) | 64% (40/40) |
| 14 (controller 1, budgets turn energy) | 80% (40/40) | 71% (40/40) | 64% (40/40) |
| 11 (controller 1 + process noise on slip (forgetting)) | 80% (40/40) | 71% (40/40) | 64% (40/40) |
| 12 (iterated extended Kalman smoother: history relinearised at smoothed st…) | 80% (40/40) | 71% (40/40) | 64% (40/40) |
| `blind` | 62% (40/40) | 62% (40/40) | 62% (40/40) |
| `cautious` | 85% (40/40) | 49% (26/40) | 32% (34/40) |
| `kristjan_reference` | 67% (40/40) | 55% (40/40) | 41% (38/40) |
| `solvi_reference` | 62% (40/40) | 42% (32/40) | 17% (4/40) |
| 16 (bound: true parameters, exact telemetry, real delay, reserve 0.5, aims…) | 88% (40/40) | 75% (40/40) | 67% (40/40) |

### Relay Pass Schedule / rush_noisy

| Controller | Delay 0 | Delay 3 | Delay 5 |
|---|---|---|---|
| 20 (cubature filter + aim at disc + turn-cost budget + window awareness) | 86% (40/40) | 70% (40/40) | 56% (40/40) |
| 26 (24 + Bayesian unmapped-sand belief (Beta prior in metres) priced on ev…) | 87% (40/40) | 69% (40/40) | 56% (40/40) |
| 19 (controller 1 + aim at disc + turn-cost budget + window awareness) | 86% (40/40) | 70% (40/40) | 56% (40/40) |
| 33 (31 plus the executive (as 32)) | 86% (40/40) | 70% (40/40) | 56% (40/40) |
| 22 (19 + battery sand odometer: unmapped sand read off the battery is adde…) | 86% (40/40) | 70% (40/40) | 56% (40/40) |
| 25 (24 + map doubt: once the map is shown wrong, undriven bedrock on the w…) | 86% (40/40) | 70% (40/40) | 56% (40/40) |
| 24 (19 + battery sand odometer (22) + stay-alive rule (23)) | 86% (40/40) | 70% (40/40) | 56% (40/40) |
| 31 (24 plus the slip-check-aware layer (as 30)) | 86% (40/40) | 70% (40/40) | 56% (40/40) |
| 23 (19 + stay-alive rule: never send a command expected to empty the batte…) | 86% (40/40) | 70% (40/40) | 56% (40/40) |
| 21 (particle filter + aim at disc + turn-cost budget + window awareness) | 86% (40/40) | 68% (40/40) | 56% (40/40) |
| 34 (27 with the guarded moves armed only when a probe is free: one telemet…) | 87% (40/40) | 70% (40/40) | 56% (40/40) |
| 28 (27 + 26's Bayesian unmapped-sand pricing on the way home) | 86% (40/40) | 68% (40/40) | 54% (40/40) |
| 27 (24 + sand-aware filter propagation + adaptive fading + guarded moves) | 86% (40/40) | 69% (40/40) | 54% (40/40) |
| 13 (controller 1, aware of uplink windows) | 85% (40/40) | 70% (40/40) | 55% (40/40) |
| 18 (controller 1 aiming at the target disc instead of its centre) | 81% (40/40) | 64% (40/40) | 54% (40/40) |
| 10 (particle filter whose slips random-walk (can follow a slip change)) | 83% (40/40) | 63% (40/40) | 54% (40/40) |
| 2 (bootstrap particle filter (500 particles) + the same planner) | 82% (40/40) | 63% (40/40) | 54% (40/40) |
| 8 (cubature Kalman filter: sigma points through the drive kinematics + th…) | 82% (40/40) | 64% (40/40) | 53% (40/40) |
| 1 (the repo's kf_mpc: EKF + delay compensation + MPC with chance constrai…) | 82% (40/40) | 64% (40/40) | 53% (40/40) |
| 32 (30 plus an executive: explicit modes switched by telemetry events (nom…) | 82% (40/40) | 64% (40/40) | 53% (40/40) |
| 29 (controller 1 for the real-time clock: measures its own lag (median of…) | 82% (40/40) | 64% (40/40) | 53% (40/40) |
| 30 (1 plus the slip-check-aware layer: a Bayesian trip chance per terrain…) | 82% (40/40) | 64% (40/40) | 53% (40/40) |
| 15 (controller 1, terrain-dependent odometry noise) | 82% (40/40) | 64% (40/40) | 53% (40/40) |
| 14 (controller 1, budgets turn energy) | 82% (40/40) | 64% (40/40) | 53% (40/40) |
| 11 (controller 1 + process noise on slip (forgetting)) | 82% (40/40) | 64% (40/40) | 53% (40/40) |
| 12 (iterated extended Kalman smoother: history relinearised at smoothed st…) | 82% (40/40) | 64% (40/40) | 53% (40/40) |
| `blind` | 56% (37/40) | 56% (38/40) | 58% (37/40) |
| `cautious` | 46% (24/40) | 37% (22/40) | 20% (19/40) |
| `kristjan_reference` | 39% (27/40) | 35% (33/40) | 27% (24/40) |
| `solvi_reference` | 50% (38/40) | 33% (29/40) | 21% (30/40) |
| 16 (bound: true parameters, exact telemetry, real delay, reserve 0.5, aims…) | 84% (40/40) | 75% (40/40) | 65% (39/40) |

### Hidden Valley / rush

| Controller | Delay 0 | Delay 3 | Delay 5 |
|---|---|---|---|
| 33 (31 plus the executive (as 32)) | 91% (40/40) | 83% (40/40) | 70% (38/40) |
| 31 (24 plus the slip-check-aware layer (as 30)) | 91% (40/40) | 81% (37/40) | 71% (39/40) |
| 32 (30 plus an executive: explicit modes switched by telemetry events (nom…) | 88% (40/40) | 80% (40/40) | 70% (38/40) |
| 18 (controller 1 aiming at the target disc instead of its centre) | 87% (38/40) | 81% (37/40) | 71% (37/40) |
| 19 (controller 1 + aim at disc + turn-cost budget + window awareness) | 87% (38/40) | 81% (37/40) | 71% (37/40) |
| 22 (19 + battery sand odometer: unmapped sand read off the battery is adde…) | 87% (38/40) | 81% (37/40) | 71% (37/40) |
| 25 (24 + map doubt: once the map is shown wrong, undriven bedrock on the w…) | 87% (38/40) | 81% (37/40) | 71% (37/40) |
| 24 (19 + battery sand odometer (22) + stay-alive rule (23)) | 87% (38/40) | 81% (37/40) | 71% (37/40) |
| 23 (19 + stay-alive rule: never send a command expected to empty the batte…) | 87% (38/40) | 81% (37/40) | 71% (37/40) |
| 20 (cubature filter + aim at disc + turn-cost budget + window awareness) | 89% (38/40) | 81% (37/40) | 71% (37/40) |
| 30 (1 plus the slip-check-aware layer: a Bayesian trip chance per terrain…) | 88% (40/40) | 78% (37/40) | 71% (38/40) |
| 26 (24 + Bayesian unmapped-sand belief (Beta prior in metres) priced on ev…) | 87% (38/40) | 81% (37/40) | 71% (37/40) |
| 34 (27 with the guarded moves armed only when a probe is free: one telemet…) | 87% (38/40) | 80% (36/40) | 71% (37/40) |
| 21 (particle filter + aim at disc + turn-cost budget + window awareness) | 88% (38/40) | 81% (37/40) | 71% (37/40) |
| 8 (cubature Kalman filter: sigma points through the drive kinematics + th…) | 86% (39/40) | 78% (37/40) | 70% (37/40) |
| 1 (the repo's kf_mpc: EKF + delay compensation + MPC with chance constrai…) | 85% (40/40) | 78% (37/40) | 70% (37/40) |
| 29 (controller 1 for the real-time clock: measures its own lag (median of…) | 85% (40/40) | 78% (37/40) | 70% (37/40) |
| 15 (controller 1, terrain-dependent odometry noise) | 85% (40/40) | 78% (37/40) | 70% (37/40) |
| 14 (controller 1, budgets turn energy) | 85% (40/40) | 78% (37/40) | 70% (37/40) |
| 13 (controller 1, aware of uplink windows) | 85% (40/40) | 78% (37/40) | 70% (37/40) |
| 12 (iterated extended Kalman smoother: history relinearised at smoothed st…) | 85% (40/40) | 78% (37/40) | 70% (37/40) |
| 2 (bootstrap particle filter (500 particles) + the same planner) | 86% (39/40) | 77% (36/40) | 70% (37/40) |
| 10 (particle filter whose slips random-walk (can follow a slip change)) | 86% (39/40) | 77% (36/40) | 70% (37/40) |
| 11 (controller 1 + process noise on slip (forgetting)) | 85% (39/40) | 79% (37/40) | 70% (37/40) |
| 27 (24 + sand-aware filter propagation + adaptive fading + guarded moves) | 87% (39/40) | 76% (36/40) | 69% (37/40) |
| 28 (27 + 26's Bayesian unmapped-sand pricing on the way home) | 87% (39/40) | 76% (36/40) | 69% (37/40) |
| `blind` | 59% (37/40) | 59% (37/40) | 59% (37/40) |
| `cautious` | 84% (38/40) | 57% (38/40) | 39% (38/40) |
| `kristjan_reference` | 67% (39/40) | 57% (37/40) | 45% (36/40) |
| `solvi_reference` | 67% (39/40) | 46% (38/40) | 32% (38/40) |
| 16 (bound: true parameters, exact telemetry, real delay, reserve 0.5, aims…) | 90% (39/40) | 81% (37/40) | 71% (37/40) |

### Hidden Valley / rush_noisy

| Controller | Delay 0 | Delay 3 | Delay 5 |
|---|---|---|---|
| 33 (31 plus the executive (as 32)) | 87% (40/40) | 73% (40/40) | 60% (39/40) |
| 31 (24 plus the slip-check-aware layer (as 30)) | 86% (40/40) | 71% (38/40) | 60% (39/40) |
| 32 (30 plus an executive: explicit modes switched by telemetry events (nom…) | 86% (40/40) | 73% (40/40) | 60% (39/40) |
| 18 (controller 1 aiming at the target disc instead of its centre) | 85% (39/40) | 70% (37/40) | 59% (38/40) |
| 19 (controller 1 + aim at disc + turn-cost budget + window awareness) | 85% (39/40) | 70% (37/40) | 59% (38/40) |
| 22 (19 + battery sand odometer: unmapped sand read off the battery is adde…) | 85% (39/40) | 70% (37/40) | 59% (38/40) |
| 25 (24 + map doubt: once the map is shown wrong, undriven bedrock on the w…) | 85% (39/40) | 70% (37/40) | 59% (38/40) |
| 24 (19 + battery sand odometer (22) + stay-alive rule (23)) | 85% (39/40) | 70% (37/40) | 59% (38/40) |
| 23 (19 + stay-alive rule: never send a command expected to empty the batte…) | 85% (39/40) | 70% (37/40) | 59% (38/40) |
| 20 (cubature filter + aim at disc + turn-cost budget + window awareness) | 85% (39/40) | 69% (36/40) | 58% (38/40) |
| 30 (1 plus the slip-check-aware layer: a Bayesian trip chance per terrain…) | 86% (40/40) | 71% (38/40) | 60% (39/40) |
| 26 (24 + Bayesian unmapped-sand belief (Beta prior in metres) priced on ev…) | 85% (39/40) | 70% (37/40) | 58% (37/40) |
| 34 (27 with the guarded moves armed only when a probe is free: one telemet…) | 85% (39/40) | 70% (37/40) | 59% (38/40) |
| 21 (particle filter + aim at disc + turn-cost budget + window awareness) | 85% (38/40) | 69% (36/40) | 58% (37/40) |
| 8 (cubature Kalman filter: sigma points through the drive kinematics + th…) | 85% (40/40) | 69% (37/40) | 58% (37/40) |
| 1 (the repo's kf_mpc: EKF + delay compensation + MPC with chance constrai…) | 84% (39/40) | 71% (38/40) | 58% (37/40) |
| 29 (controller 1 for the real-time clock: measures its own lag (median of…) | 84% (39/40) | 71% (38/40) | 58% (37/40) |
| 15 (controller 1, terrain-dependent odometry noise) | 84% (39/40) | 71% (38/40) | 58% (37/40) |
| 14 (controller 1, budgets turn energy) | 84% (39/40) | 71% (38/40) | 58% (37/40) |
| 13 (controller 1, aware of uplink windows) | 84% (39/40) | 71% (38/40) | 58% (37/40) |
| 12 (iterated extended Kalman smoother: history relinearised at smoothed st…) | 84% (40/40) | 71% (38/40) | 58% (37/40) |
| 2 (bootstrap particle filter (500 particles) + the same planner) | 86% (40/40) | 69% (36/40) | 58% (37/40) |
| 10 (particle filter whose slips random-walk (can follow a slip change)) | 85% (38/40) | 69% (36/40) | 58% (37/40) |
| 11 (controller 1 + process noise on slip (forgetting)) | 84% (38/40) | 69% (36/40) | 58% (37/40) |
| 27 (24 + sand-aware filter propagation + adaptive fading + guarded moves) | 85% (39/40) | 69% (38/40) | 57% (38/40) |
| 28 (27 + 26's Bayesian unmapped-sand pricing on the way home) | 84% (39/40) | 69% (38/40) | 57% (37/40) |
| `blind` | 56% (37/40) | 54% (36/40) | 56% (36/40) |
| `cautious` | 20% (10/40) | 39% (25/40) | 25% (25/40) |
| `kristjan_reference` | 42% (24/40) | 21% (18/40) | 27% (24/40) |
| `solvi_reference` | 51% (37/40) | 35% (34/40) | 23% (27/40) |
| 16 (bound: true parameters, exact telemetry, real delay, reserve 0.5, aims…) | 86% (37/40) | 80% (38/40) | 70% (37/40) |

### Bagnold Dunes / rush

| Controller | Delay 0 | Delay 3 | Delay 5 |
|---|---|---|---|
| 34 (27 with the guarded moves armed only when a probe is free: one telemet…) | 88% (40/40) | 81% (40/40) | 70% (40/40) |
| 25 (24 + map doubt: once the map is shown wrong, undriven bedrock on the w…) | 88% (40/40) | 81% (40/40) | 70% (40/40) |
| 33 (31 plus the executive (as 32)) | 88% (40/40) | 82% (40/40) | 70% (40/40) |
| 22 (19 + battery sand odometer: unmapped sand read off the battery is adde…) | 88% (40/40) | 82% (40/40) | 70% (40/40) |
| 24 (19 + battery sand odometer (22) + stay-alive rule (23)) | 88% (40/40) | 82% (40/40) | 70% (40/40) |
| 31 (24 plus the slip-check-aware layer (as 30)) | 88% (40/40) | 82% (40/40) | 70% (40/40) |
| 20 (cubature filter + aim at disc + turn-cost budget + window awareness) | 88% (40/40) | 82% (40/40) | 70% (40/40) |
| 26 (24 + Bayesian unmapped-sand belief (Beta prior in metres) priced on ev…) | 88% (40/40) | 82% (39/40) | 71% (40/40) |
| 18 (controller 1 aiming at the target disc instead of its centre) | 88% (40/40) | 82% (40/40) | 70% (40/40) |
| 19 (controller 1 + aim at disc + turn-cost budget + window awareness) | 88% (40/40) | 82% (40/40) | 70% (40/40) |
| 23 (19 + stay-alive rule: never send a command expected to empty the batte…) | 88% (40/40) | 82% (40/40) | 70% (40/40) |
| 28 (27 + 26's Bayesian unmapped-sand pricing on the way home) | 88% (40/40) | 79% (40/40) | 69% (40/40) |
| 27 (24 + sand-aware filter propagation + adaptive fading + guarded moves) | 88% (40/40) | 79% (40/40) | 69% (40/40) |
| 21 (particle filter + aim at disc + turn-cost budget + window awareness) | 86% (39/40) | 81% (39/40) | 69% (39/40) |
| 8 (cubature Kalman filter: sigma points through the drive kinematics + th…) | 86% (40/40) | 77% (39/40) | 69% (39/40) |
| 1 (the repo's kf_mpc: EKF + delay compensation + MPC with chance constrai…) | 86% (40/40) | 77% (40/40) | 69% (39/40) |
| 32 (30 plus an executive: explicit modes switched by telemetry events (nom…) | 86% (40/40) | 77% (40/40) | 69% (39/40) |
| 29 (controller 1 for the real-time clock: measures its own lag (median of…) | 86% (40/40) | 77% (40/40) | 69% (39/40) |
| 30 (1 plus the slip-check-aware layer: a Bayesian trip chance per terrain…) | 86% (40/40) | 77% (40/40) | 69% (39/40) |
| 15 (controller 1, terrain-dependent odometry noise) | 86% (40/40) | 77% (40/40) | 69% (39/40) |
| 14 (controller 1, budgets turn energy) | 86% (40/40) | 77% (40/40) | 69% (39/40) |
| 13 (controller 1, aware of uplink windows) | 86% (40/40) | 77% (40/40) | 69% (39/40) |
| 11 (controller 1 + process noise on slip (forgetting)) | 86% (40/40) | 76% (39/40) | 69% (39/40) |
| 12 (iterated extended Kalman smoother: history relinearised at smoothed st…) | 86% (40/40) | 77% (40/40) | 69% (39/40) |
| 10 (particle filter whose slips random-walk (can follow a slip change)) | 84% (40/40) | 78% (39/40) | 69% (39/40) |
| 2 (bootstrap particle filter (500 particles) + the same planner) | 84% (40/40) | 78% (40/40) | 69% (39/40) |
| `blind` | 57% (36/40) | 56% (35/40) | 56% (35/40) |
| `cautious` | 87% (40/40) | 60% (40/40) | 40% (40/40) |
| `kristjan_reference` | 70% (40/40) | 59% (40/40) | 48% (40/40) |
| `solvi_reference` | 69% (40/40) | 49% (40/40) | 33% (39/40) |
| 16 (bound: true parameters, exact telemetry, real delay, reserve 0.5, aims…) | 89% (40/40) | 78% (39/40) | 70% (40/40) |

### Bagnold Dunes / rush_noisy

| Controller | Delay 0 | Delay 3 | Delay 5 |
|---|---|---|---|
| 34 (27 with the guarded moves armed only when a probe is free: one telemet…) | 86% (40/40) | 71% (40/40) | 62% (40/40) |
| 25 (24 + map doubt: once the map is shown wrong, undriven bedrock on the w…) | 87% (40/40) | 70% (39/40) | 60% (40/40) |
| 33 (31 plus the executive (as 32)) | 87% (40/40) | 69% (39/40) | 60% (40/40) |
| 22 (19 + battery sand odometer: unmapped sand read off the battery is adde…) | 87% (40/40) | 69% (39/40) | 60% (40/40) |
| 24 (19 + battery sand odometer (22) + stay-alive rule (23)) | 87% (40/40) | 69% (39/40) | 60% (40/40) |
| 31 (24 plus the slip-check-aware layer (as 30)) | 87% (40/40) | 69% (39/40) | 60% (40/40) |
| 20 (cubature filter + aim at disc + turn-cost budget + window awareness) | 85% (40/40) | 70% (39/40) | 60% (39/40) |
| 26 (24 + Bayesian unmapped-sand belief (Beta prior in metres) priced on ev…) | 86% (39/40) | 69% (38/40) | 61% (40/40) |
| 18 (controller 1 aiming at the target disc instead of its centre) | 87% (40/40) | 69% (39/40) | 60% (40/40) |
| 19 (controller 1 + aim at disc + turn-cost budget + window awareness) | 87% (40/40) | 69% (39/40) | 60% (40/40) |
| 23 (19 + stay-alive rule: never send a command expected to empty the batte…) | 87% (40/40) | 69% (39/40) | 60% (40/40) |
| 28 (27 + 26's Bayesian unmapped-sand pricing on the way home) | 86% (40/40) | 69% (40/40) | 60% (40/40) |
| 27 (24 + sand-aware filter propagation + adaptive fading + guarded moves) | 86% (40/40) | 69% (40/40) | 60% (40/40) |
| 21 (particle filter + aim at disc + turn-cost budget + window awareness) | 85% (40/40) | 69% (38/40) | 59% (39/40) |
| 8 (cubature Kalman filter: sigma points through the drive kinematics + th…) | 86% (40/40) | 70% (39/40) | 60% (39/40) |
| 1 (the repo's kf_mpc: EKF + delay compensation + MPC with chance constrai…) | 85% (40/40) | 71% (40/40) | 59% (39/40) |
| 32 (30 plus an executive: explicit modes switched by telemetry events (nom…) | 85% (40/40) | 71% (40/40) | 59% (39/40) |
| 29 (controller 1 for the real-time clock: measures its own lag (median of…) | 85% (40/40) | 71% (40/40) | 59% (39/40) |
| 30 (1 plus the slip-check-aware layer: a Bayesian trip chance per terrain…) | 85% (40/40) | 71% (40/40) | 59% (39/40) |
| 15 (controller 1, terrain-dependent odometry noise) | 85% (40/40) | 71% (40/40) | 59% (39/40) |
| 14 (controller 1, budgets turn energy) | 85% (40/40) | 71% (40/40) | 59% (39/40) |
| 13 (controller 1, aware of uplink windows) | 85% (40/40) | 71% (40/40) | 59% (39/40) |
| 11 (controller 1 + process noise on slip (forgetting)) | 86% (40/40) | 69% (39/40) | 60% (39/40) |
| 12 (iterated extended Kalman smoother: history relinearised at smoothed st…) | 85% (40/40) | 69% (39/40) | 59% (39/40) |
| 10 (particle filter whose slips random-walk (can follow a slip change)) | 83% (37/40) | 69% (38/40) | 59% (38/40) |
| 2 (bootstrap particle filter (500 particles) + the same planner) | 83% (37/40) | 69% (38/40) | 58% (38/40) |
| `blind` | 53% (36/40) | 53% (37/40) | 54% (35/40) |
| `cautious` | 20% (9/40) | 39% (25/40) | 28% (26/40) |
| `kristjan_reference` | 40% (23/40) | 19% (16/40) | 26% (23/40) |
| `solvi_reference` | 52% (38/40) | 36% (36/40) | 24% (28/40) |
| 16 (bound: true parameters, exact telemetry, real delay, reserve 0.5, aims…) | 88% (40/40) | 78% (39/40) | 69% (38/40) |

### Troy Crust / rush

| Controller | Delay 0 | Delay 3 | Delay 5 |
|---|---|---|---|
| 26 (24 + Bayesian unmapped-sand belief (Beta prior in metres) priced on ev…) | 84% (40/40) | 76% (40/40) | 64% (40/40) |
| 34 (27 with the guarded moves armed only when a probe is free: one telemet…) | 84% (40/40) | 76% (40/40) | 63% (38/40) |
| 11 (controller 1 + process noise on slip (forgetting)) | 85% (40/40) | 77% (40/40) | 66% (39/40) |
| 33 (31 plus the executive (as 32)) | 84% (40/40) | 76% (40/40) | 63% (39/40) |
| 22 (19 + battery sand odometer: unmapped sand read off the battery is adde…) | 84% (40/40) | 76% (40/40) | 63% (39/40) |
| 24 (19 + battery sand odometer (22) + stay-alive rule (23)) | 84% (40/40) | 76% (40/40) | 63% (39/40) |
| 31 (24 plus the slip-check-aware layer (as 30)) | 84% (40/40) | 76% (40/40) | 63% (39/40) |
| 25 (24 + map doubt: once the map is shown wrong, undriven bedrock on the w…) | 84% (40/40) | 76% (40/40) | 63% (40/40) |
| 18 (controller 1 aiming at the target disc instead of its centre) | 85% (40/40) | 75% (39/40) | 63% (40/40) |
| 19 (controller 1 + aim at disc + turn-cost budget + window awareness) | 85% (40/40) | 75% (39/40) | 63% (40/40) |
| 23 (19 + stay-alive rule: never send a command expected to empty the batte…) | 85% (40/40) | 75% (39/40) | 63% (40/40) |
| 8 (cubature Kalman filter: sigma points through the drive kinematics + th…) | 85% (40/40) | 76% (40/40) | 66% (39/40) |
| 1 (the repo's kf_mpc: EKF + delay compensation + MPC with chance constrai…) | 84% (40/40) | 76% (40/40) | 65% (39/40) |
| 32 (30 plus an executive: explicit modes switched by telemetry events (nom…) | 84% (40/40) | 76% (40/40) | 65% (39/40) |
| 29 (controller 1 for the real-time clock: measures its own lag (median of…) | 84% (40/40) | 76% (40/40) | 65% (39/40) |
| 30 (1 plus the slip-check-aware layer: a Bayesian trip chance per terrain…) | 84% (40/40) | 76% (40/40) | 65% (39/40) |
| 15 (controller 1, terrain-dependent odometry noise) | 84% (40/40) | 76% (40/40) | 65% (39/40) |
| 14 (controller 1, budgets turn energy) | 84% (40/40) | 76% (40/40) | 65% (39/40) |
| 13 (controller 1, aware of uplink windows) | 84% (40/40) | 76% (40/40) | 65% (39/40) |
| 20 (cubature filter + aim at disc + turn-cost budget + window awareness) | 83% (40/40) | 75% (39/40) | 63% (39/40) |
| 12 (iterated extended Kalman smoother: history relinearised at smoothed st…) | 84% (40/40) | 76% (40/40) | 65% (39/40) |
| 28 (27 + 26's Bayesian unmapped-sand pricing on the way home) | 83% (40/40) | 74% (39/40) | 62% (38/40) |
| 27 (24 + sand-aware filter propagation + adaptive fading + guarded moves) | 83% (40/40) | 74% (39/40) | 61% (38/40) |
| 10 (particle filter whose slips random-walk (can follow a slip change)) | 79% (40/40) | 72% (38/40) | 65% (39/40) |
| 21 (particle filter + aim at disc + turn-cost budget + window awareness) | 76% (40/40) | 74% (39/40) | 62% (37/40) |
| 2 (bootstrap particle filter (500 particles) + the same planner) | 79% (40/40) | 72% (39/40) | 65% (39/40) |
| `blind` | 54% (34/40) | 56% (35/40) | 55% (34/40) |
| `cautious` | 84% (40/40) | 56% (38/40) | 40% (39/40) |
| `solvi_reference` | 67% (40/40) | 46% (38/40) | 32% (38/40) |
| `kristjan_reference` | 70% (40/40) | 58% (39/40) | 46% (40/40) |
| 16 (bound: true parameters, exact telemetry, real delay, reserve 0.5, aims…) | 86% (40/40) | 81% (40/40) | 72% (40/40) |

### Troy Crust / rush_noisy

| Controller | Delay 0 | Delay 3 | Delay 5 |
|---|---|---|---|
| 26 (24 + Bayesian unmapped-sand belief (Beta prior in metres) priced on ev…) | 83% (40/40) | 67% (40/40) | 59% (40/40) |
| 34 (27 with the guarded moves armed only when a probe is free: one telemet…) | 84% (40/40) | 68% (39/40) | 58% (39/40) |
| 11 (controller 1 + process noise on slip (forgetting)) | 82% (38/40) | 67% (40/40) | 55% (37/40) |
| 33 (31 plus the executive (as 32)) | 83% (40/40) | 65% (39/40) | 59% (40/40) |
| 22 (19 + battery sand odometer: unmapped sand read off the battery is adde…) | 83% (40/40) | 65% (39/40) | 59% (40/40) |
| 24 (19 + battery sand odometer (22) + stay-alive rule (23)) | 83% (40/40) | 65% (39/40) | 59% (40/40) |
| 31 (24 plus the slip-check-aware layer (as 30)) | 83% (40/40) | 65% (39/40) | 59% (40/40) |
| 25 (24 + map doubt: once the map is shown wrong, undriven bedrock on the w…) | 83% (40/40) | 65% (39/40) | 59% (40/40) |
| 18 (controller 1 aiming at the target disc instead of its centre) | 84% (40/40) | 66% (39/40) | 57% (39/40) |
| 19 (controller 1 + aim at disc + turn-cost budget + window awareness) | 84% (40/40) | 66% (39/40) | 57% (39/40) |
| 23 (19 + stay-alive rule: never send a command expected to empty the batte…) | 84% (40/40) | 66% (39/40) | 57% (39/40) |
| 8 (cubature Kalman filter: sigma points through the drive kinematics + th…) | 83% (39/40) | 64% (38/40) | 56% (39/40) |
| 1 (the repo's kf_mpc: EKF + delay compensation + MPC with chance constrai…) | 83% (39/40) | 64% (38/40) | 56% (38/40) |
| 32 (30 plus an executive: explicit modes switched by telemetry events (nom…) | 83% (39/40) | 64% (38/40) | 56% (38/40) |
| 29 (controller 1 for the real-time clock: measures its own lag (median of…) | 83% (39/40) | 64% (38/40) | 56% (38/40) |
| 30 (1 plus the slip-check-aware layer: a Bayesian trip chance per terrain…) | 83% (39/40) | 64% (38/40) | 56% (38/40) |
| 15 (controller 1, terrain-dependent odometry noise) | 83% (39/40) | 64% (38/40) | 56% (38/40) |
| 14 (controller 1, budgets turn energy) | 83% (39/40) | 64% (38/40) | 56% (38/40) |
| 13 (controller 1, aware of uplink windows) | 83% (39/40) | 64% (38/40) | 56% (38/40) |
| 20 (cubature filter + aim at disc + turn-cost budget + window awareness) | 84% (40/40) | 65% (39/40) | 57% (39/40) |
| 12 (iterated extended Kalman smoother: history relinearised at smoothed st…) | 82% (39/40) | 63% (38/40) | 56% (39/40) |
| 28 (27 + 26's Bayesian unmapped-sand pricing on the way home) | 83% (40/40) | 67% (39/40) | 57% (40/40) |
| 27 (24 + sand-aware filter propagation + adaptive fading + guarded moves) | 83% (40/40) | 66% (39/40) | 57% (40/40) |
| 10 (particle filter whose slips random-walk (can follow a slip change)) | 79% (37/40) | 66% (39/40) | 56% (38/40) |
| 21 (particle filter + aim at disc + turn-cost budget + window awareness) | 79% (39/40) | 67% (40/40) | 57% (39/40) |
| 2 (bootstrap particle filter (500 particles) + the same planner) | 79% (39/40) | 65% (38/40) | 55% (37/40) |
| `blind` | 51% (34/40) | 50% (33/40) | 53% (33/40) |
| `cautious` | 11% (5/40) | 39% (26/40) | 27% (29/40) |
| `solvi_reference` | 49% (36/40) | 34% (36/40) | 23% (25/40) |
| `kristjan_reference` | 38% (21/40) | 19% (16/40) | 16% (13/40) |
| 16 (bound: true parameters, exact telemetry, real delay, reserve 0.5, aims…) | 84% (39/40) | 78% (39/40) | 67% (37/40) |

### Gale Rock Field / rush

| Controller | Delay 0 | Delay 3 | Delay 5 |
|---|---|---|---|
| 34 (27 with the guarded moves armed only when a probe is free: one telemet…) | 87% (40/40) | 76% (40/40) | 66% (40/40) |
| 21 (particle filter + aim at disc + turn-cost budget + window awareness) | 86% (40/40) | 76% (40/40) | 64% (39/40) |
| 26 (24 + Bayesian unmapped-sand belief (Beta prior in metres) priced on ev…) | 87% (40/40) | 75% (40/40) | 67% (40/40) |
| 25 (24 + map doubt: once the map is shown wrong, undriven bedrock on the w…) | 87% (40/40) | 75% (40/40) | 66% (40/40) |
| 18 (controller 1 aiming at the target disc instead of its centre) | 87% (40/40) | 75% (40/40) | 66% (40/40) |
| 19 (controller 1 + aim at disc + turn-cost budget + window awareness) | 87% (40/40) | 75% (40/40) | 66% (40/40) |
| 33 (31 plus the executive (as 32)) | 87% (40/40) | 75% (40/40) | 66% (40/40) |
| 22 (19 + battery sand odometer: unmapped sand read off the battery is adde…) | 87% (40/40) | 75% (40/40) | 66% (40/40) |
| 24 (19 + battery sand odometer (22) + stay-alive rule (23)) | 87% (40/40) | 75% (40/40) | 66% (40/40) |
| 31 (24 plus the slip-check-aware layer (as 30)) | 87% (40/40) | 75% (40/40) | 66% (40/40) |
| 23 (19 + stay-alive rule: never send a command expected to empty the batte…) | 87% (40/40) | 75% (40/40) | 66% (40/40) |
| 20 (cubature filter + aim at disc + turn-cost budget + window awareness) | 87% (40/40) | 75% (40/40) | 65% (39/40) |
| 10 (particle filter whose slips random-walk (can follow a slip change)) | 84% (40/40) | 75% (40/40) | 64% (40/40) |
| 2 (bootstrap particle filter (500 particles) + the same planner) | 84% (40/40) | 74% (40/40) | 64% (39/40) |
| 8 (cubature Kalman filter: sigma points through the drive kinematics + th…) | 84% (40/40) | 74% (40/40) | 64% (40/40) |
| 12 (iterated extended Kalman smoother: history relinearised at smoothed st…) | 84% (40/40) | 74% (40/40) | 65% (40/40) |
| 1 (the repo's kf_mpc: EKF + delay compensation + MPC with chance constrai…) | 84% (40/40) | 74% (40/40) | 65% (40/40) |
| 32 (30 plus an executive: explicit modes switched by telemetry events (nom…) | 84% (40/40) | 74% (40/40) | 65% (40/40) |
| 29 (controller 1 for the real-time clock: measures its own lag (median of…) | 84% (40/40) | 74% (40/40) | 65% (40/40) |
| 30 (1 plus the slip-check-aware layer: a Bayesian trip chance per terrain…) | 84% (40/40) | 74% (40/40) | 65% (40/40) |
| 15 (controller 1, terrain-dependent odometry noise) | 84% (40/40) | 74% (40/40) | 65% (40/40) |
| 14 (controller 1, budgets turn energy) | 84% (40/40) | 74% (40/40) | 65% (40/40) |
| 13 (controller 1, aware of uplink windows) | 84% (40/40) | 74% (40/40) | 65% (40/40) |
| 11 (controller 1 + process noise on slip (forgetting)) | 84% (40/40) | 74% (40/40) | 65% (40/40) |
| 28 (27 + 26's Bayesian unmapped-sand pricing on the way home) | 87% (40/40) | 74% (40/40) | 60% (38/40) |
| 27 (24 + sand-aware filter propagation + adaptive fading + guarded moves) | 87% (40/40) | 74% (40/40) | 61% (39/40) |
| `blind` | 47% (28/40) | 45% (26/40) | 44% (25/40) |
| `cautious` | 85% (40/40) | 56% (38/40) | 38% (38/40) |
| `kristjan_reference` | 70% (40/40) | 53% (40/40) | 40% (39/40) |
| `solvi_reference` | 68% (40/40) | 43% (33/40) | 28% (34/40) |
| 16 (bound: true parameters, exact telemetry, real delay, reserve 0.5, aims…) | 89% (40/40) | 78% (40/40) | 67% (39/40) |

### Gale Rock Field / rush_noisy

| Controller | Delay 0 | Delay 3 | Delay 5 |
|---|---|---|---|
| 34 (27 with the guarded moves armed only when a probe is free: one telemet…) | 84% (40/40) | 66% (40/40) | 55% (40/40) |
| 21 (particle filter + aim at disc + turn-cost budget + window awareness) | 85% (40/40) | 66% (40/40) | 56% (40/40) |
| 26 (24 + Bayesian unmapped-sand belief (Beta prior in metres) priced on ev…) | 84% (40/40) | 65% (40/40) | 55% (39/40) |
| 25 (24 + map doubt: once the map is shown wrong, undriven bedrock on the w…) | 83% (40/40) | 66% (40/40) | 55% (40/40) |
| 18 (controller 1 aiming at the target disc instead of its centre) | 83% (40/40) | 66% (40/40) | 55% (40/40) |
| 19 (controller 1 + aim at disc + turn-cost budget + window awareness) | 83% (40/40) | 66% (40/40) | 55% (40/40) |
| 33 (31 plus the executive (as 32)) | 83% (40/40) | 66% (40/40) | 55% (40/40) |
| 22 (19 + battery sand odometer: unmapped sand read off the battery is adde…) | 83% (40/40) | 66% (40/40) | 55% (40/40) |
| 24 (19 + battery sand odometer (22) + stay-alive rule (23)) | 83% (40/40) | 66% (40/40) | 55% (40/40) |
| 31 (24 plus the slip-check-aware layer (as 30)) | 83% (40/40) | 66% (40/40) | 55% (40/40) |
| 23 (19 + stay-alive rule: never send a command expected to empty the batte…) | 83% (40/40) | 66% (40/40) | 55% (40/40) |
| 20 (cubature filter + aim at disc + turn-cost budget + window awareness) | 84% (40/40) | 66% (40/40) | 55% (40/40) |
| 10 (particle filter whose slips random-walk (can follow a slip change)) | 83% (40/40) | 67% (40/40) | 56% (40/40) |
| 2 (bootstrap particle filter (500 particles) + the same planner) | 84% (40/40) | 67% (40/40) | 56% (40/40) |
| 8 (cubature Kalman filter: sigma points through the drive kinematics + th…) | 83% (40/40) | 66% (40/40) | 54% (40/40) |
| 12 (iterated extended Kalman smoother: history relinearised at smoothed st…) | 82% (40/40) | 67% (40/40) | 54% (40/40) |
| 1 (the repo's kf_mpc: EKF + delay compensation + MPC with chance constrai…) | 82% (40/40) | 66% (40/40) | 54% (40/40) |
| 32 (30 plus an executive: explicit modes switched by telemetry events (nom…) | 82% (40/40) | 66% (40/40) | 54% (40/40) |
| 29 (controller 1 for the real-time clock: measures its own lag (median of…) | 82% (40/40) | 66% (40/40) | 54% (40/40) |
| 30 (1 plus the slip-check-aware layer: a Bayesian trip chance per terrain…) | 82% (40/40) | 66% (40/40) | 54% (40/40) |
| 15 (controller 1, terrain-dependent odometry noise) | 82% (40/40) | 66% (40/40) | 54% (40/40) |
| 14 (controller 1, budgets turn energy) | 82% (40/40) | 66% (40/40) | 54% (40/40) |
| 13 (controller 1, aware of uplink windows) | 82% (40/40) | 66% (40/40) | 54% (40/40) |
| 11 (controller 1 + process noise on slip (forgetting)) | 81% (40/40) | 67% (40/40) | 54% (39/40) |
| 28 (27 + 26's Bayesian unmapped-sand pricing on the way home) | 84% (40/40) | 64% (39/40) | 53% (40/40) |
| 27 (24 + sand-aware filter propagation + adaptive fading + guarded moves) | 84% (40/40) | 63% (39/40) | 52% (40/40) |
| `blind` | 43% (26/40) | 39% (22/40) | 45% (26/40) |
| `cautious` | 14% (6/40) | 38% (23/40) | 24% (21/40) |
| `kristjan_reference` | 41% (24/40) | 24% (22/40) | 19% (16/40) |
| `solvi_reference` | 52% (38/40) | 33% (32/40) | 20% (20/40) |
| 16 (bound: true parameters, exact telemetry, real delay, reserve 0.5, aims…) | 89% (40/40) | 76% (40/40) | 65% (39/40) |

### Meridiani Ripple Plains / rush

| Controller | Delay 0 | Delay 3 | Delay 5 |
|---|---|---|---|
| 10 (particle filter whose slips random-walk (can follow a slip change)) | 88% (40/40) | 73% (40/40) | 61% (40/40) |
| 21 (particle filter + aim at disc + turn-cost budget + window awareness) | 88% (40/40) | 73% (40/40) | 62% (40/40) |
| 18 (controller 1 aiming at the target disc instead of its centre) | 87% (40/40) | 73% (40/40) | 62% (40/40) |
| 19 (controller 1 + aim at disc + turn-cost budget + window awareness) | 87% (40/40) | 73% (40/40) | 62% (40/40) |
| 33 (31 plus the executive (as 32)) | 87% (40/40) | 73% (40/40) | 62% (40/40) |
| 22 (19 + battery sand odometer: unmapped sand read off the battery is adde…) | 87% (40/40) | 73% (40/40) | 62% (40/40) |
| 25 (24 + map doubt: once the map is shown wrong, undriven bedrock on the w…) | 87% (40/40) | 73% (40/40) | 62% (40/40) |
| 24 (19 + battery sand odometer (22) + stay-alive rule (23)) | 87% (40/40) | 73% (40/40) | 62% (40/40) |
| 31 (24 plus the slip-check-aware layer (as 30)) | 87% (40/40) | 73% (40/40) | 62% (40/40) |
| 23 (19 + stay-alive rule: never send a command expected to empty the batte…) | 87% (40/40) | 73% (40/40) | 62% (40/40) |
| 2 (bootstrap particle filter (500 particles) + the same planner) | 88% (40/40) | 73% (40/40) | 61% (40/40) |
| 34 (27 with the guarded moves armed only when a probe is free: one telemet…) | 87% (40/40) | 73% (40/40) | 62% (40/40) |
| 11 (controller 1 + process noise on slip (forgetting)) | 88% (40/40) | 73% (40/40) | 61% (40/40) |
| 26 (24 + Bayesian unmapped-sand belief (Beta prior in metres) priced on ev…) | 87% (40/40) | 73% (40/40) | 62% (40/40) |
| 1 (the repo's kf_mpc: EKF + delay compensation + MPC with chance constrai…) | 87% (40/40) | 73% (40/40) | 61% (40/40) |
| 32 (30 plus an executive: explicit modes switched by telemetry events (nom…) | 87% (40/40) | 73% (40/40) | 61% (40/40) |
| 29 (controller 1 for the real-time clock: measures its own lag (median of…) | 87% (40/40) | 73% (40/40) | 61% (40/40) |
| 30 (1 plus the slip-check-aware layer: a Bayesian trip chance per terrain…) | 87% (40/40) | 73% (40/40) | 61% (40/40) |
| 14 (controller 1, budgets turn energy) | 87% (40/40) | 73% (40/40) | 61% (40/40) |
| 13 (controller 1, aware of uplink windows) | 87% (40/40) | 73% (40/40) | 61% (40/40) |
| 8 (cubature Kalman filter: sigma points through the drive kinematics + th…) | 87% (40/40) | 73% (40/40) | 61% (40/40) |
| 20 (cubature filter + aim at disc + turn-cost budget + window awareness) | 87% (40/40) | 72% (40/40) | 62% (40/40) |
| 15 (controller 1, terrain-dependent odometry noise) | 87% (40/40) | 73% (40/40) | 61% (40/40) |
| 12 (iterated extended Kalman smoother: history relinearised at smoothed st…) | 87% (40/40) | 73% (40/40) | 61% (40/40) |
| 27 (24 + sand-aware filter propagation + adaptive fading + guarded moves) | 87% (40/40) | 71% (40/40) | 60% (40/40) |
| 28 (27 + 26's Bayesian unmapped-sand pricing on the way home) | 86% (40/40) | 72% (40/40) | 60% (40/40) |
| `blind` | 56% (37/40) | 56% (38/40) | 58% (37/40) |
| `solvi_reference` | 52% (38/40) | 35% (35/40) | 24% (28/40) |
| `cautious` | 20% (9/40) | 40% (24/40) | 27% (26/40) |
| `kristjan_reference` | 42% (23/40) | 23% (21/40) | 22% (20/40) |
| 16 (bound: true parameters, exact telemetry, real delay, reserve 0.5, aims…) | 90% (40/40) | 84% (40/40) | 73% (40/40) |

### Meridiani Ripple Plains / rush_noisy

| Controller | Delay 0 | Delay 3 | Delay 5 |
|---|---|---|---|
| 10 (particle filter whose slips random-walk (can follow a slip change)) | 88% (40/40) | 73% (40/40) | 61% (40/40) |
| 21 (particle filter + aim at disc + turn-cost budget + window awareness) | 88% (40/40) | 73% (40/40) | 62% (40/40) |
| 18 (controller 1 aiming at the target disc instead of its centre) | 87% (40/40) | 73% (40/40) | 62% (40/40) |
| 19 (controller 1 + aim at disc + turn-cost budget + window awareness) | 87% (40/40) | 73% (40/40) | 62% (40/40) |
| 33 (31 plus the executive (as 32)) | 87% (40/40) | 73% (40/40) | 62% (40/40) |
| 22 (19 + battery sand odometer: unmapped sand read off the battery is adde…) | 87% (40/40) | 73% (40/40) | 62% (40/40) |
| 25 (24 + map doubt: once the map is shown wrong, undriven bedrock on the w…) | 87% (40/40) | 73% (40/40) | 62% (40/40) |
| 24 (19 + battery sand odometer (22) + stay-alive rule (23)) | 87% (40/40) | 73% (40/40) | 62% (40/40) |
| 31 (24 plus the slip-check-aware layer (as 30)) | 87% (40/40) | 73% (40/40) | 62% (40/40) |
| 23 (19 + stay-alive rule: never send a command expected to empty the batte…) | 87% (40/40) | 73% (40/40) | 62% (40/40) |
| 2 (bootstrap particle filter (500 particles) + the same planner) | 88% (40/40) | 73% (40/40) | 61% (40/40) |
| 34 (27 with the guarded moves armed only when a probe is free: one telemet…) | 87% (40/40) | 73% (40/40) | 62% (40/40) |
| 11 (controller 1 + process noise on slip (forgetting)) | 88% (40/40) | 73% (40/40) | 61% (40/40) |
| 26 (24 + Bayesian unmapped-sand belief (Beta prior in metres) priced on ev…) | 87% (40/40) | 73% (40/40) | 62% (40/40) |
| 1 (the repo's kf_mpc: EKF + delay compensation + MPC with chance constrai…) | 87% (40/40) | 73% (40/40) | 61% (40/40) |
| 32 (30 plus an executive: explicit modes switched by telemetry events (nom…) | 87% (40/40) | 73% (40/40) | 61% (40/40) |
| 29 (controller 1 for the real-time clock: measures its own lag (median of…) | 87% (40/40) | 73% (40/40) | 61% (40/40) |
| 30 (1 plus the slip-check-aware layer: a Bayesian trip chance per terrain…) | 87% (40/40) | 73% (40/40) | 61% (40/40) |
| 14 (controller 1, budgets turn energy) | 87% (40/40) | 73% (40/40) | 61% (40/40) |
| 13 (controller 1, aware of uplink windows) | 87% (40/40) | 73% (40/40) | 61% (40/40) |
| 8 (cubature Kalman filter: sigma points through the drive kinematics + th…) | 87% (40/40) | 73% (40/40) | 61% (40/40) |
| 20 (cubature filter + aim at disc + turn-cost budget + window awareness) | 87% (40/40) | 72% (40/40) | 62% (40/40) |
| 15 (controller 1, terrain-dependent odometry noise) | 87% (40/40) | 73% (40/40) | 61% (40/40) |
| 12 (iterated extended Kalman smoother: history relinearised at smoothed st…) | 87% (40/40) | 73% (40/40) | 61% (40/40) |
| 27 (24 + sand-aware filter propagation + adaptive fading + guarded moves) | 87% (40/40) | 71% (40/40) | 60% (40/40) |
| 28 (27 + 26's Bayesian unmapped-sand pricing on the way home) | 86% (40/40) | 72% (40/40) | 60% (40/40) |
| `blind` | 56% (37/40) | 56% (38/40) | 58% (37/40) |
| `solvi_reference` | 52% (38/40) | 35% (35/40) | 24% (28/40) |
| `cautious` | 20% (9/40) | 40% (24/40) | 27% (26/40) |
| `kristjan_reference` | 42% (23/40) | 23% (21/40) | 22% (20/40) |
| 16 (bound: true parameters, exact telemetry, real delay, reserve 0.5, aims…) | 90% (40/40) | 84% (40/40) | 73% (40/40) |

