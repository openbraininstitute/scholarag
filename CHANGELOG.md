# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- Fix whitespace issue in author suggestion

## [0.0.7] - 30.10.2024

### Added
- Auto push to ecr.

## [0.0.6] - 19.09.2024

### Fixed
- Streaming with cache enabled.

### Changed
- Use OpenAI response_format instead of separators in the prompt.
- Switch to cohere reranker v3 and `retriever_k = 500`.

## [v0.0.5]

### Changed
- Put SSL certification for OS in the application by default.

### Removed
- Remove `user-id` from the caching key building.

## [v0.0.4]

### Added
- First full release
