from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from openai import AsyncOpenAI, OpenAI

# from openai.types.chat.chat_completion import
from openai.lib.streaming.chat import ChunkEvent, ContentDoneEvent
from openai.types.chat import (
    ParsedChatCompletion,
    ParsedChatCompletionMessage,
    ParsedChoice,
)
from openai.types.chat.chat_completion_chunk import (
    ChatCompletionChunk,
    Choice,
    ChoiceDelta,
)
from openai.types.completion_usage import CompletionUsage
from scholarag.generative_question_answering import (
    GenerativeQAOutput,
    GenerativeQAWithSources,
)


def test_run():
    fake_llm = Mock(spec=OpenAI(api_key="sasda"))
    gaq = GenerativeQAWithSources(client=fake_llm, model="gpt-ni.colas-turbo")
    query = "How nice is this context ?"
    context = [
        "This context is very nice.",
        "I really enjoyed this context.",
        "That's really an amazing context.",
    ]
    fake_response = ParsedChatCompletion[GenerativeQAOutput](
        id="chatcmpl-A3L1rdVJUsgqGkDku7H0Lv2cjpEUS",
        choices=[
            ParsedChoice[GenerativeQAOutput](
                finish_reason="stop",
                index=0,
                logprobs=None,
                message=ParsedChatCompletionMessage[GenerativeQAOutput](
                    content='{"has_answer":true,"answer":"Very nice.","paragraphs":[0]}',
                    refusal=None,
                    role="assistant",
                    function_call=None,
                    tool_calls=[],
                    parsed=GenerativeQAOutput(
                        has_answer=True, answer="Very nice.", paragraphs=[0]
                    ),
                ),
            )
        ],
        created=1725359183,
        model="gpt-4o-mini-2024-07-18",
        object="chat.completion",
        service_tier=None,
        system_fingerprint="fp_f33667828e",
        usage=CompletionUsage(
            completion_tokens=107, prompt_tokens=2706, total_tokens=2813
        ),
    )

    # Test with well formated output.
    fake_llm.beta.chat.completions.parse.return_value = fake_response
    result, finish_reason = gaq.run(query=query, contexts=context)
    assert result == GenerativeQAOutput(
        has_answer=True, answer="Very nice.", paragraphs=[0]
    )
    assert finish_reason == "stop"

    # Test multiple sources. Correct format
    fake_response.choices[0].finish_reason = None
    fake_response.choices[
        0
    ].message.content = '{"has_answer":true,"answer":"Very nice.","paragraphs":[0,1]}'
    fake_response.choices[0].message.parsed = GenerativeQAOutput(
        has_answer=True, answer="Very nice.", paragraphs=[0, 1]
    )
    result, finish_reason = gaq.run(query=query, contexts=context)
    assert result == GenerativeQAOutput(
        has_answer=True, answer="Very nice.", paragraphs=[0, 1]
    )
    assert finish_reason is None

    # No answer.
    fake_response.choices[0].finish_reason = "stop"
    fake_response.choices[
        0
    ].message.content = '{"has_answer":false,"answer":"I dont know","paragraphs":[]}'
    fake_response.choices[0].message.parsed = GenerativeQAOutput(
        has_answer=False, answer="I dont know.", paragraphs=[]
    )
    result, finish_reason = gaq.run(query=query, contexts=context)
    assert result == GenerativeQAOutput(
        has_answer=False, answer="I dont know.", paragraphs=[]
    )
    assert finish_reason == "stop"


@pytest.mark.asyncio
async def test_arun():
    fake_llm = AsyncMock(spec=AsyncOpenAI(api_key="assdas"))
    create_output = AsyncMock()
    gaq = GenerativeQAWithSources(client=fake_llm, model="gpt-ni.colas-turbo")
    query = "How nice is this context ?"
    context = [
        "This context is very nice.",
        "I really enjoyed this context.",
        "That's really an amazing context.",
    ]
    create_output.return_value = ParsedChatCompletion[GenerativeQAOutput](
        id="chatcmpl-A3L1rdVJUsgqGkDku7H0Lv2cjpEUS",
        choices=[
            ParsedChoice[GenerativeQAOutput](
                finish_reason="stop",
                index=0,
                logprobs=None,
                message=ParsedChatCompletionMessage[GenerativeQAOutput](
                    content='{"has_answer":true,"answer":"Very nice.","paragraphs":[0]}',
                    refusal=None,
                    role="assistant",
                    function_call=None,
                    tool_calls=[],
                    parsed=GenerativeQAOutput(
                        has_answer=True, answer="Very nice.", paragraphs=[0]
                    ),
                ),
            )
        ],
        created=1725359183,
        model="gpt-4o-mini-2024-07-18",
        object="chat.completion",
        service_tier=None,
        system_fingerprint="fp_f33667828e",
        usage=CompletionUsage(
            completion_tokens=107, prompt_tokens=2706, total_tokens=2813
        ),
    )

    # Single source.
    fake_llm.beta.chat.completions.parse = create_output
    result, finish_reason = await gaq.arun(query=query, contexts=context)
    assert result == GenerativeQAOutput(
        has_answer=True, answer="Very nice.", paragraphs=[0]
    )
    assert finish_reason == "stop"

    # Multiple sources.
    create_output.return_value.choices[0].finish_reason = "length"
    create_output.return_value.choices[
        0
    ].message.content = '{"has_answer":true,"answer":"Very nice.","paragraphs":[0,1]}'
    create_output.return_value.choices[0].message.parsed = GenerativeQAOutput(
        has_answer=True, answer="Very nice.", paragraphs=[0, 1]
    )
    result, finish_reason = await gaq.arun(query=query, contexts=context)
    assert result == GenerativeQAOutput(
        has_answer=True, answer="Very nice.", paragraphs=[0, 1]
    )
    assert finish_reason == "length"

    # No answer.
    create_output.return_value.choices[0].finish_reason = "stop"
    create_output.return_value.choices[
        0
    ].message.content = '{"has_answer":false,"answer":"I dont know","paragraphs":[]}'
    create_output.return_value.choices[0].message.parsed = GenerativeQAOutput(
        has_answer=False, answer="I dont know.", paragraphs=[]
    )
    result, finish_reason = await gaq.arun(query=query, contexts=context)
    assert result == GenerativeQAOutput(
        has_answer=False, answer="I dont know.", paragraphs=[]
    )
    assert finish_reason == "stop"


def stream(**kwargs):
    base_response = ChunkEvent(
        type="chunk",
        chunk=ChatCompletionChunk(
            id="chatcmpl-A3NV8ibLOiAzjjYSJtj7qV4fqx1Tc",
            choices=[
                Choice(
                    delta=ChoiceDelta(
                        content="",
                        function_call=None,
                        refusal=None,
                        role="assistant",
                        tool_calls=None,
                    ),
                    finish_reason=None,
                    index=0,
                    logprobs=None,
                )
            ],
            created=1725368686,
            model="gpt-schola.rag-maxi",
            object="chat.completion.chunk",
            service_tier=None,
            system_fingerprint="fp_5bd87c427a",
            usage=None,
        ),
        snapshot=ParsedChatCompletion[object](
            id="chatcmpl-A3NV8ibLOiAzjjYSJtj7qV4fqx1Tc",
            choices=[
                ParsedChoice[object](
                    finish_reason="stop",
                    index=0,
                    logprobs=None,
                    message=ParsedChatCompletionMessage[object](
                        content="",
                        refusal=None,
                        role="assistant",
                        function_call=None,
                        tool_calls=None,
                        parsed=None,
                    ),
                )
            ],
            created=1725368686,
            model="gpt-4o-mini-2024-07-18",
            object="chat.completion",
            service_tier=None,
            system_fingerprint="fp_5bd87c427a",
            usage=None,
        ),
    )
    to_stream = (
        '{"has_answer": true, "answer": "I am a great answer.", "paragraphs": [0,1]}'
    )
    yield base_response
    for word in to_stream.split(" "):
        base_response.chunk.choices[0].delta.content = (
            word + " " if word != "[0,1]}" else word
        )
        yield base_response

    # Chunk containing the finish reasom
    yield ChunkEvent(
        type="chunk",
        chunk=ChatCompletionChunk(
            id="chatcmpl-A3OP6fNcncOnNJUcMVVxWaPenNBWl",
            choices=[
                Choice(
                    delta=ChoiceDelta(
                        content=None,
                        function_call=None,
                        refusal=None,
                        role=None,
                        tool_calls=None,
                    ),
                    finish_reason="stop",
                    index=0,
                    logprobs=None,
                )
            ],
            created=1725372156,
            model="gpt-4o-mini-2024-07-18",
            object="chat.completion.chunk",
            service_tier=None,
            system_fingerprint="fp_f33667828e",
            usage=None,
        ),
        snapshot=ParsedChatCompletion[object](
            id="chatcmpl-A3OP6fNcncOnNJUcMVVxWaPenNBWl",
            choices=[
                ParsedChoice[object](
                    finish_reason="stop",
                    index=0,
                    logprobs=None,
                    message=ParsedChatCompletionMessage[object](
                        content='{"has_answer": true, "answer": "I am a great answer.", "paragraphs": [0,1]}',
                        refusal=None,
                        role="assistant",
                        function_call=None,
                        tool_calls=None,
                        parsed=GenerativeQAOutput(
                            has_answer=True,
                            answer="I am a great answer.",
                            paragraphs=[0, 1],
                        ),
                    ),
                )
            ],
            created=1725372156,
            model="gpt-schola.rag-maxi",
            object="chat.completion",
            service_tier=None,
            system_fingerprint="fp_f33667828e",
            usage=None,
        ),
    )

    # Chunk containing the parsed output
    yield ContentDoneEvent[GenerativeQAOutput](
        type="content.done",
        content='{"has_answer": true, "answer": "I am a great answer.","paragraphs": [0,1]}',
        parsed=GenerativeQAOutput(
            has_answer=True, answer="I am a great answer.", paragraphs=[0, 1]
        ),
    )

    # Chunk containing the usage
    yield ChunkEvent(
        type="chunk",
        chunk=ChatCompletionChunk(
            id="chatcmpl-A3NZvqwHHblDdW19Vs1RyFd06xRc3",
            choices=[],
            created=1725368983,
            model="gpt-schola.rag-maxi",
            object="chat.completion.chunk",
            service_tier=None,
            system_fingerprint="fp_f33667828e",
            usage=CompletionUsage(
                completion_tokens=85, prompt_tokens=2677, total_tokens=2762
            ),
        ),
        snapshot=ParsedChatCompletion[object](
            id="chatcmpl-A3NZvqwHHblDdW19Vs1RyFd06xRc3",
            choices=[
                ParsedChoice[object](
                    finish_reason="stop",
                    index=0,
                    logprobs=None,
                    message=ParsedChatCompletionMessage[object](
                        content='{"has_answer": true, "answer": "I am a great answer.", "paragraphs": [0,1]}',
                        refusal=None,
                        role="assistant",
                        function_call=None,
                        tool_calls=None,
                        parsed=GenerativeQAOutput(
                            has_answer=True,
                            answer="I am a great answer.",
                            paragraphs=[0, 1],
                        ),
                    ),
                )
            ],
            created=1725368983,
            model="gpt-schola.rag-maxi",
            object="chat.completion",
            service_tier=None,
            system_fingerprint="fp_f33667828e",
            usage=CompletionUsage(
                completion_tokens=85, prompt_tokens=2677, total_tokens=2762
            ),
        ),
    )


async def astream(**kwargs):
    for elem in stream(**kwargs):
        yield elem


def test_stream():
    fake_llm = Mock(spec=OpenAI(api_key="assdas"))
    gaq = GenerativeQAWithSources(client=fake_llm, model="gpt-schola.rag-maxi")
    query = "How nice is this context ?"
    context = [
        "This context is very nice.",
        "I really enjoyed this context.",
        "That's really an amazing context.",
    ]
    stream_mock = MagicMock()
    stream_mock.__enter__.return_value = stream()
    stream_mock.__exit__.return_value = None

    fake_llm.beta.chat.completions.stream.return_value = stream_mock

    streamed_gen = gaq.stream(query, context)
    try:
        partial_text = ""
        while True:
            chunk, _ = next(streamed_gen)
            partial_text += chunk
    except StopIteration as err:
        finish_reason = err.value
    assert (
        partial_text
        == '{"has_answer": true, "answer": "I am a great answer.", "paragraphs": [0,1]}'
    )
    assert finish_reason == "stop"


@pytest.mark.asyncio
async def test_astream():
    fake_llm = AsyncMock(spec=AsyncOpenAI(api_key="assdas"))
    gaq = GenerativeQAWithSources(client=fake_llm, model="gpt-schola.rag-maxi")
    query = "How nice is this context ?"
    context = [
        "This context is very nice.",
        "I really enjoyed this context.",
        "That's really an amazing context.",
    ]
    stream_mock = MagicMock()
    stream_mock.__aenter__.return_value = astream()
    stream_mock.__aexit__.return_value = None

    # fake_create = AsyncMock()
    # fake_create.return_value = astream()
    fake_llm.beta.chat.completions.stream.return_value = stream_mock
    try:
        partial_text = ""
        async for chunk, _ in gaq.astream(query, context):
            partial_text += chunk
    except RuntimeError as err:
        finish_reason = err.args[0]
    assert (
        partial_text
        == '{"has_answer": true, "answer": "I am a great answer.", "paragraphs": [0,1]}'
    )
    assert finish_reason == "stop"
