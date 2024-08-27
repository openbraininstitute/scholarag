"""Run the parsing routine."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from httpx import AsyncClient, AsyncHTTPTransport, Response
from httpx._exceptions import HTTPError
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ParsingService(BaseModel):
    """Class to parse files.

    Parameters
    ----------
    ignore_errors
        Controls whether the code should raise an exception and stop upon having a request with non 2xx status code.
    max_concurrent_requests
        Maximum number of requests that can be sent simultaneously to the server.
    """

    max_concurrent_requests: int | None = None
    ignore_errors: bool = True

    def run(
        self,
        files: list[Path] | list[bytes],
        url: str,
        multipart_params: dict[str, Any] | None = None,
        timeout: int | None = None,
        httpx_client: AsyncClient | None = None,
    ) -> list[dict[str, Any] | None]:
        """Parse one or multiple files.

        Parameters
        ----------
        files
            Files to parse.
        url
            Url of the parser.
        multipart_params
            Optional request parameters to go along with the file. NOT QUERY PARAMETERS.
        timeout
            Timeout of HTTP requests.
        httpx_client
            Async HTTP Client (Optional)

        Returns
        -------
        parsed: list[dict[str, Any] | None]
            Parsing of the files.
        """
        logger.info(f"Parsing {len(files)} files")
        # create payload
        parsed = asyncio.run(
            self.arun(
                files=files,
                url=url,
                multipart_params=multipart_params,
                timeout=timeout,
                httpx_client=httpx_client,
            )
        )

        return parsed

    async def arun(
        self,
        files: list[Path] | list[bytes],
        url: str,
        multipart_params: dict[str, Any] | None = None,
        timeout: int | None = None,
        httpx_client: AsyncClient | None = None,
    ) -> list[dict[str, str | list[str] | None] | None]:
        """Call async the ETL API.

        Parameters
        ----------
        files
            List of file path or bytes that have to be parsed.
        url
            URL of the target ETL API.
        multipart_params
            Optional parameters to go along with the file. NOT QUERY PARAMETERS. Relevant for pdfs.
        timeout
            Sets global timeout for http requests.
        httpx_client
            Async HTTPx Client.

        Returns
        -------
        output: list[dict[str, str | list[str] | None] | None]
            Output of the requests.
        """
        logger.info(f"Parsing {len(files)} files")
        if self.max_concurrent_requests is not None:
            semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        else:
            semaphore = None

        async with AsyncExitStack() as stack:
            # If the httpx client is None, create it and enter the context manager.
            # This way the client gets closed after sending requests.
            # If the httpx client is provided, we don't close it so that
            # it can be reused. It becomes the user's responsibility to close it.
            if httpx_client is None:
                transport = AsyncHTTPTransport(retries=6)
                httpx_client = AsyncClient(timeout=timeout, transport=transport)
                await stack.enter_async_context(httpx_client)

            tasks = [
                asyncio.create_task(
                    self.asend_request(
                        httpx_client=httpx_client,
                        url=url,
                        file=file,
                        multipart_params=multipart_params,
                        semaphore=semaphore,
                    )
                )
                for file in files
            ]
            res = await asyncio.gather(*tasks, return_exceptions=self.ignore_errors)

        output = [
            (
                response.json()
                if isinstance(response, Response) and response.status_code // 100 == 2
                else None
            )
            for response in res
        ]
        return output

    @staticmethod
    async def asend_request(
        httpx_client: AsyncClient,
        url: str,
        file: Path | bytes,
        multipart_params: dict[str, Any] | None = None,
        semaphore: asyncio.Semaphore | None = None,
    ) -> Response:
        """Call the specified ETL API and returns parsed files.

        Parameters
        ----------
        httpx_client
            Client to use to send the requests.
        url
            URL of the target API.
        file
            Body of the request to send. Should be preferably batched
        multipart_params
            Optional parameters to go along with the file. NOT QUERY PARAMETERS.
        semaphore
            asyncio.Semaphore class used to limit the number of simultaneously outgoing requests.

        Returns
        -------
        result: Response
            Output of the request.
        """
        async with semaphore if semaphore is not None else AsyncExitStack():  # type: ignore
            try:
                # Multipart params for pdfs. Must be "{}" if empty.
                data = {"parameters": json.dumps(multipart_params)}

                if isinstance(file, Path):
                    with file.open("rb") as f:
                        files = [("inp", (file.name, f, "text/xml"))]
                        logger.debug(f"Sending request for file {files[0][1][0]}")
                        result = await httpx_client.post(url, files=files, data=data)
                        logger.debug(
                            f"Received request for file {files[0][1][0]}. response"
                            f" code: {result.status_code}"
                        )
                elif isinstance(file, bytes):
                    logger.debug("Sending bytes contained in the body.")
                    file_bytes = [("inp", ("text.xml", file, "text/xml"))]
                    result = await httpx_client.post(url, files=file_bytes, data=data)
                    logger.debug("Reiceved bytes contained in the body.")
                else:
                    raise ValueError(
                        "Wrong body type for task etl. It should be a pathlib.Path or"
                        " bytes."
                    )

                if result.status_code != 200:
                    file_str = file.decode() if isinstance(file, bytes) else file
                    raise ValueError(
                        f"Something wrong happened for the body {file_str}. "
                        f"The status code is {result.status_code}."
                    )

            except HTTPError as err:
                file_str = file.decode() if isinstance(file, bytes) else file
                raise HTTPError(
                    f"Something wrong happened for the body {file_str}"
                ) from err
        return result
