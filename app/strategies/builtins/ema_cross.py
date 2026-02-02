def schema():
    return {
        "id": "ema_cross",
        "name": "EMA Cross (V2)",
        "inputs": {
            "fast": {"type": "int", "default": 12, "min": 1, "max": 200},
            "slow": {"type": "int", "default": 26, "min": 1, "max": 200},
            "size_pct": {"type": "float", "default": 0.1, "min": 0.001, "max": 1.0},
        },
    }


def on_init(ctx):
    ctx.state["armed"] = True


def on_bar(ctx, i):
    fast = ctx.ind.ema(ctx.close, int(ctx.params["fast"]))
    slow = ctx.ind.ema(ctx.close, int(ctx.params["slow"]))
    if i < 1:
        return
    cross_up = fast[i] > slow[i] and fast[i - 1] <= slow[i - 1]
    cross_dn = fast[i] < slow[i] and fast[i - 1] >= slow[i - 1]
    if cross_up and ctx.position.size == 0:
        size = ctx.size.percent_equity(float(ctx.params["size_pct"]))
        if size > 0:
            ctx.buy(size)
    if cross_dn and ctx.position.size != 0:
        ctx.flatten()
