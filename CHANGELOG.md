# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.0.12] - 09.05.2025

### Changed
- Reranking based on text + abstract + title.
- Match on text + title.

## [0.0.11] - 05.05.2025

### Changed
- Author resolving in retrievals.

## [0.0.10] - 26.02.2025

### Changed
- Better search algorithm for article count / listing.

## [0.0.9] - 14.02.2025

### Added
- Bearer token insertion in FastAPI UI.

### Fixed
- Limit query size.
- Add OBI copyright.
- Push to ECR prod+staging

## [0.0.8] - 10.12.2024

### Fixed
- Fix whitespace issue in author suggestion.

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
