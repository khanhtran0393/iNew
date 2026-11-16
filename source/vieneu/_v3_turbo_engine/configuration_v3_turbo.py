"""Model configuration for V3 Turbo."""

class V3TurboConfig:
    def __init__(self, sample_rate: int = 24000, hidden_dim: int = 512, **kwargs):
        self.sample_rate = sample_rate
        self.hidden_dim = hidden_dim
