## original behavior

```sh
flux-local build hr hr-with-crd --path clusters/dev --no-skip-crds
```

That should not include a `CustomResourceDefinition`. since flux-local originally doesn't pass `--include-crds` into `helm template`. Only `ConfigMap` should be rendered

```sh
flux-local build hr hr-with-crd --path clusters/dev --skip-crds
```

That should not include the `CustomResourceDefinition` and keep the `ConfigMap`.

## behavior of https://github.com/neodejack/flux-local/commit/07ef6156a49c003fb09555b0272cf29ebea7c1c8

i have a local copy of https://github.com/neodejack/flux-local/commit/07ef6156a49c003fb09555b0272cf29ebea7c1c8 at path `/Users/zilizhang/tmp/flux-local/.venv/bin/flux-local`

```sh
/Users/zilizhang/tmp/flux-local/.venv/bin/flux-local build hr hr-with-crd --path clusters/dev --no-skip-crds
```

That should include a `CustomResourceDefinition`.

```sh
/Users/zilizhang/tmp/flux-local/.venv/bin/flux-local build hr hr-with-crd --path clusters/dev --skip-crds
```

That should not include the `CustomResourceDefinition` and keep the `ConfigMap`.
