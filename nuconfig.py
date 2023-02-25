import toml

with open(f"config.toml", encoding="utf8") as cfg:
    NuConfig = toml.load(cfg)
    print(NuConfig.keys())
