"""Launcher for the original ThunderAgent router.

Works around an upstream packaging bug: ThunderAgent/__init__.py imports
.app at package import time, and app.py builds its module-level router at
import with the DEFAULT config. So when the `thunderagent` CLI later calls
set_config() in __main__.main(), the already-created router keeps
backends=['http://localhost:8000'] and profiling/scheduler settings from
the defaults - the CLI flags are silently ignored.

This launcher uses the upstream documented embedding API (Config,
MultiBackendRouter, register_routes) to build the router with the intended
config before any request handling. No upstream source is modified.
"""
import argparse


def main() -> None:
    p = argparse.ArgumentParser(description="Original ThunderAgent (embedding API launcher)")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8300)
    p.add_argument("--backends", required=True, help="Comma-separated vLLM backend URLs")
    p.add_argument("--router", default="tr", choices=["default", "tr"])
    p.add_argument("--backend-type", default="vllm", choices=["vllm", "sglang", "skyrl"])
    p.add_argument("--profile", action="store_true")
    p.add_argument("--metrics", action="store_true")
    p.add_argument("--metrics-interval", type=float, default=5.0)
    p.add_argument("--scheduler-interval", type=float, default=5.0)
    p.add_argument("--acting-token-weight", type=float, default=1.0)
    p.add_argument("--use-acting-token-decay", action="store_true")
    args = p.parse_args()

    from ThunderAgent import Config, MultiBackendRouter, register_routes, set_config

    backends = [b.strip() for b in args.backends.split(",") if b.strip()]
    config = Config(
        backends=backends,
        router_mode=args.router,
        backend_type=args.backend_type,
        profile_enabled=args.profile,
        metrics_enabled=args.metrics,
        metrics_interval=args.metrics_interval,
        scheduler_interval=args.scheduler_interval,
        acting_token_weight=args.acting_token_weight,
        use_acting_token_decay=args.use_acting_token_decay,
    )
    set_config(config)

    router = MultiBackendRouter(
        backends,
        profile_enabled=config.profile_enabled,
        scheduling_enabled=(config.router_mode == "tr"),
        scheduler_interval=config.scheduler_interval,
        backend_type=config.backend_type,
        acting_token_weight=config.acting_token_weight,
        use_acting_token_decay=config.use_acting_token_decay,
    )

    from fastapi import FastAPI

    app = FastAPI(title="ThunderAgent (original) - paper verification")

    @app.on_event("startup")
    async def _start() -> None:
        await router.start()

    @app.on_event("shutdown")
    async def _stop() -> None:
        await router.stop()

    register_routes(app, router, config)

    print(f"launcher: router_mode={args.router} backends={backends}")

    import uvicorn

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
