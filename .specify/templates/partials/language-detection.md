# Language Detection Patterns

Reusable patterns for detecting programming languages and frameworks in a codebase.

## Detection Logic

### JavaScript/TypeScript
**Identifying Files**: `package.json`, `tsconfig.json`, `next.config.js`, `vite.config.ts`

```bash
cat package.json | jq '{name, dependencies, devDependencies, scripts}'
# Framework clues: "next" → Next.js, "vite" → Vite, "@nestjs" → NestJS
```

### Python
**Identifying Files**: `requirements.txt`, `pyproject.toml`, `setup.py`, `Pipfile`, `poetry.lock`

```bash
cat requirements.txt | head -20
grep -E "django|fastapi|flask|tornado" requirements.txt
cat pyproject.toml | grep "\[tool.poetry\]"
```

### Go
**Identifying Files**: `go.mod`, `go.sum`

```bash
cat go.mod | grep "^module\|^require"
# Framework clues: "gin-gonic" → Gin, "echo" → Echo, "fiber" → Fiber
```

### Java/Kotlin
**Identifying Files**: `pom.xml`, `build.gradle`, `build.gradle.kts`

```bash
grep -E "<groupId>|<artifactId>" pom.xml | head -10
grep -E "org.springframework|jakarta." pom.xml # → Spring Boot
cat build.gradle | grep "dependencies"
```

### PHP
**Identifying Files**: `composer.json`, `artisan` (Laravel)

```bash
cat composer.json | jq '.require'
# Framework clues: "laravel/framework" → Laravel, "symfony/" → Symfony
```

### Rust
**Identifying Files**: `Cargo.toml`

```bash
cat Cargo.toml | grep "\[dependencies\]"
grep -E "actix-web|rocket|axum" Cargo.toml # → Web framework
```

### Ruby
**Identifying Files**: `Gemfile`, `Gemfile.lock`

```bash
cat Gemfile | grep "gem"
grep "rails" Gemfile # → Rails
```

## Detection Command

```bash
# Scan root for identifying files (check ALL, not just one)
ls -la | grep -E "package.json|go.mod|requirements.txt|pyproject.toml|setup.py|Pipfile|pom.xml|build.gradle|composer.json|Cargo.toml|Gemfile"
```

## Output Fields

- **Primary Language(s)**: (can be multi-language, e.g., "go,typescript")
- **Framework**: Next.js, React, Vue, Express, NestJS, Gin, Echo, Django, FastAPI, Flask, Spring Boot, Laravel, Symfony, Rails, Actix-Web
- **Build Tools**: npm, yarn, pnpm, pip, poetry, maven, gradle, cargo, composer
