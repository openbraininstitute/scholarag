from unittest.mock import AsyncMock, Mock

import pytest
from openai import AsyncOpenAI, OpenAI
from openai.types.chat import ChatCompletion, ChatCompletionChunk, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice as RunChoice
from openai.types.chat.chat_completion_chunk import Choice, ChoiceDelta
from openai.types.completion_usage import CompletionUsage
from scholarag.generative_question_answering import (
    SOURCES_SEPARATOR,
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
    fake_response = ChatCompletion(
        id="chatcmpl-9k86ZK0uY65mPo1PvdnueBmD8hFLK",
        choices=[
            RunChoice(
                finish_reason="stop",
                index=0,
                logprobs=None,
                message=ChatCompletionMessage(
                    content=f"Very nice.\n{SOURCES_SEPARATOR}: 0",
                    role="assistant",
                    function_call=None,
                    tool_calls=None,
                ),
            )
        ],
        created=1720781271,
        model="bbp-3.5",
        object="chat.completion",
        service_tier=None,
        system_fingerprint=None,
        usage=CompletionUsage(
            completion_tokens=87, prompt_tokens=12236, total_tokens=12323
        ),
    )
    # Test with well formated output.
    fake_llm.chat.completions.create.return_value = fake_response
    result, finish_reason = gaq.run(query=query, contexts=context)
    assert result == {
        "answer": "Very nice.",
        "paragraphs": [0],
        "raw_answer": f"Very nice.\n{SOURCES_SEPARATOR}: 0",
    }
    assert finish_reason == "stop"
    # Test with a badly returned context that still makes sense.
    fake_response.choices[
        0
    ].message.content = f"Very nice.\n{SOURCES_SEPARATOR}: This context is very nice."
    result, finish_reason = gaq.run(query=query, contexts=context)
    assert result == {
        "answer": None,
        "paragraphs": None,
        "raw_answer": f"Very nice.\n{SOURCES_SEPARATOR}: This context is very nice.",
    }
    assert finish_reason == "stop"
    # Test with a badly formatted output but the context is in the source.
    fake_response.choices[0].message.content = (
        f"Very nice.\n{SOURCES_SEPARATOR}: This context is very nice.\nQUESTION: How"
        " nice is this context ?"
    )
    fake_response.choices[0].finish_reason = "length"
    result, finish_reason = gaq.run(query=query, contexts=context)
    assert result == {
        "answer": None,
        "paragraphs": None,
        "raw_answer": (
            f"Very nice.\n{SOURCES_SEPARATOR}: This context is very"
            " nice.\nQUESTION: How nice is this context ?"
        ),
    }
    assert finish_reason == "length"
    # Test with a completely messed up output format
    fake_response.choices[
        0
    ].message.content = (
        "Very nice. This context is very nice.\nQUESTION: How nice is this context ?"
    )
    result, finish_reason = gaq.run(query=query, contexts=context)
    assert result == {
        "answer": None,
        "paragraphs": None,
        "raw_answer": (
            "Very nice. This context is very nice.\nQUESTION: How nice is this"
            " context ?"
        ),
    }
    assert finish_reason == "length"
    # Test multiple sources. Correct format
    fake_response.choices[0].finish_reason = None
    fake_response.choices[0].message.content = f"Very nice.\n{SOURCES_SEPARATOR}: 0, 1"
    result, finish_reason = gaq.run(query=query, contexts=context)
    assert result == {
        "answer": "Very nice.",
        "paragraphs": [0, 1],
        "raw_answer": f"Very nice.\n{SOURCES_SEPARATOR}: 0, 1",
    }
    assert finish_reason is None

    # Test multiple sources. Sources returned not number
    fake_response.choices[0].message.content = (
        f"Very nice.\n{SOURCES_SEPARATOR}: This context is very nice., I really enjoyed"
        " this context."
    )
    result, finish_reason = gaq.run(query=query, contexts=context)
    assert result == {
        "answer": None,
        "paragraphs": None,
        "raw_answer": (
            f"Very nice.\n{SOURCES_SEPARATOR}: This context is very nice., I really"
            " enjoyed this context."
        ),
    }

    # Test multiple sources. Wrong layout but sources still present.
    fake_response.choices[0].message.content = (
        f"Very nice.\n{SOURCES_SEPARATOR}: This context is very nice. I really enjoyed"
        " this context.\nQUESTION: How nice is this context ?"
    )
    result, finish_reason = gaq.run(query=query, contexts=context)
    assert result == {
        "answer": None,
        "paragraphs": None,
        "raw_answer": (
            f"Very nice.\n{SOURCES_SEPARATOR}: This context is very nice. I really"
            " enjoyed this context.\nQUESTION: How nice is this context ?"
        ),
    }


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
    create_output.return_value = ChatCompletion(
        id="chatcmpl-9k86ZK0uY65mPo1PvdnueBmD8hFLK",
        choices=[
            RunChoice(
                finish_reason="stop",
                index=0,
                logprobs=None,
                message=ChatCompletionMessage(
                    content=f"Very nice.\n{SOURCES_SEPARATOR}: 0",
                    role="assistant",
                    function_call=None,
                    tool_calls=None,
                ),
            )
        ],
        created=1720781271,
        model="bbp-3.5",
        object="chat.completion",
        service_tier=None,
        system_fingerprint=None,
        usage=CompletionUsage(
            completion_tokens=87, prompt_tokens=12236, total_tokens=12323
        ),
    )
    # Test with well formated output.
    fake_llm.chat.completions.create = create_output
    result, finish_reason = await gaq.arun(query=query, contexts=context)
    assert result == {
        "answer": "Very nice.",
        "paragraphs": [0],
        "raw_answer": f"Very nice.\n{SOURCES_SEPARATOR}: 0",
    }
    assert finish_reason == "stop"
    # Test with a badly returned context that still makes sense.
    create_output.return_value.choices[
        0
    ].message.content = f"Very nice.\n{SOURCES_SEPARATOR}: This context is very nice."
    result, finish_reason = await gaq.arun(query=query, contexts=context)
    assert result == {
        "answer": None,
        "paragraphs": None,
        "raw_answer": f"Very nice.\n{SOURCES_SEPARATOR}: This context is very nice.",
    }
    assert finish_reason == "stop"
    # Test with a badly formatted output but the context is in the source.
    create_output.return_value.choices[0].message.content = (
        f"Very nice.\n{SOURCES_SEPARATOR}: This context is very nice.\nQUESTION: How"
        " nice is this context ?"
    )
    create_output.return_value.choices[0].finish_reason = "length"
    result, finish_reason = await gaq.arun(query=query, contexts=context)
    assert result == {
        "answer": None,
        "paragraphs": None,
        "raw_answer": (
            f"Very nice.\n{SOURCES_SEPARATOR}: This context is very"
            " nice.\nQUESTION: How nice is this context ?"
        ),
    }
    assert finish_reason == "length"
    # Test with a completely messed up output format
    create_output.return_value.choices[
        0
    ].message.content = (
        "Very nice. This context is very nice.\nQUESTION: How nice is this context ?"
    )
    result, finish_reason = await gaq.arun(query=query, contexts=context)
    assert result == {
        "answer": None,
        "paragraphs": None,
        "raw_answer": (
            "Very nice. This context is very nice.\nQUESTION: How nice is this"
            " context ?"
        ),
    }
    assert finish_reason == "length"
    # Test multiple sources. Correct format
    create_output.return_value.choices[0].finish_reason = None
    create_output.return_value.choices[
        0
    ].message.content = f"Very nice.\n{SOURCES_SEPARATOR}: 0, 1"
    result, finish_reason = await gaq.arun(query=query, contexts=context)
    assert result == {
        "answer": "Very nice.",
        "paragraphs": [0, 1],
        "raw_answer": f"Very nice.\n{SOURCES_SEPARATOR}: 0, 1",
    }
    assert finish_reason is None

    # Test multiple sources. Sources returned not number
    create_output.return_value.choices[0].message.content = (
        f"Very nice.\n{SOURCES_SEPARATOR}: This context is very nice., I really enjoyed"
        " this context."
    )
    result, finish_reason = await gaq.arun(query=query, contexts=context)
    assert result == {
        "answer": None,
        "paragraphs": None,
        "raw_answer": (
            f"Very nice.\n{SOURCES_SEPARATOR}: This context is very nice., I really"
            " enjoyed this context."
        ),
    }

    # Test multiple sources. Wrong layout but sources still present.
    create_output.return_value.choices[0].message.content = (
        f"Very nice.\n{SOURCES_SEPARATOR}: This context is very nice. I really enjoyed"
        " this context.\nQUESTION: How nice is this context ?"
    )
    result, finish_reason = await gaq.arun(query=query, contexts=context)
    assert result == {
        "answer": None,
        "paragraphs": None,
        "raw_answer": (
            f"Very nice.\n{SOURCES_SEPARATOR}: This context is very nice. I really"
            " enjoyed this context.\nQUESTION: How nice is this context ?"
        ),
    }


def stream(**kwargs):
    base_response = ChatCompletionChunk(
        id="chatcmpl-9kBJNLoYybxyGe9pxsZkY3XgZMg8t",
        choices=[
            Choice(
                delta=ChoiceDelta(
                    content="", function_call=None, role="assistant", tool_calls=None
                ),
                finish_reason=None,
                index=0,
                logprobs=None,
            )
        ],
        created=1720793597,
        model="gpt-ni.colas-turbo",
        object="chat.completion.chunk",
        service_tier=None,
        system_fingerprint=None,
        usage=None,
    )
    to_stream = f"I am a great answer. {SOURCES_SEPARATOR}\n 0, 1"
    yield base_response
    for word in to_stream.split(" "):
        base_response.choices[0].delta.content = word + " " if word != "1" else word
        yield base_response
    yield ChatCompletionChunk(
        id="chatcmpl-9kBOdgQkrwK9yRbx7VXIiBXwTnKea",
        choices=[
            Choice(
                delta=ChoiceDelta(
                    content=None, function_call=None, role=None, tool_calls=None
                ),
                finish_reason="stop",
                index=0,
                logprobs=None,
            )
        ],
        created=1720793923,
        model="gpt-ni.colas-turbo",
        object="chat.completion.chunk",
        service_tier=None,
        system_fingerprint=None,
        usage=None,
    )
    yield ChatCompletionChunk(
        id="chatcmpl-9kBOdgQkrwK9yRbx7VXIiBXwTnKea",
        choices=[],
        created=1720793923,
        model="gpt-ni.ciolas-turbo",
        object="chat.completion.chunk",
        service_tier=None,
        system_fingerprint=None,
        usage=CompletionUsage(
            completion_tokens=15, prompt_tokens=3935, total_tokens=3950
        ),
    )


async def astream(**kwargs):
    base_response = ChatCompletionChunk(
        id="chatcmpl-9kBJNLoYybxyGe9pxsZkY3XgZMg8t",
        choices=[
            Choice(
                delta=ChoiceDelta(
                    content="", function_call=None, role="assistant", tool_calls=None
                ),
                finish_reason=None,
                index=0,
                logprobs=None,
            )
        ],
        created=1720793597,
        model="gpt-ni.colas-turbo",
        object="chat.completion.chunk",
        service_tier=None,
        system_fingerprint=None,
        usage=None,
    )
    to_stream = f"I am a great answer. {SOURCES_SEPARATOR}\n 0, 1"
    yield base_response
    for word in to_stream.split(" "):
        base_response.choices[0].delta.content = word + " " if word != "1" else word
        yield base_response
    yield ChatCompletionChunk(
        id="chatcmpl-9kBOdgQkrwK9yRbx7VXIiBXwTnKea",
        choices=[
            Choice(
                delta=ChoiceDelta(
                    content=None, function_call=None, role=None, tool_calls=None
                ),
                finish_reason="stop",
                index=0,
                logprobs=None,
            )
        ],
        created=1720793923,
        model="gpt-ni.colas-turbo",
        object="chat.completion.chunk",
        service_tier=None,
        system_fingerprint=None,
        usage=None,
    )
    yield ChatCompletionChunk(
        id="chatcmpl-9kBOdgQkrwK9yRbx7VXIiBXwTnKea",
        choices=[],
        created=1720793923,
        model="gpt-ni.ciolas-turbo",
        object="chat.completion.chunk",
        service_tier=None,
        system_fingerprint=None,
        usage=CompletionUsage(
            completion_tokens=15, prompt_tokens=3935, total_tokens=3950
        ),
    )


def test_stream():
    fake_llm = Mock(spec=OpenAI(api_key="assdas"))
    gaq = GenerativeQAWithSources(client=fake_llm, model="gpt-ni.colas-turbo")
    query = "How nice is this context ?"
    context = [
        "This context is very nice.",
        "I really enjoyed this context.",
        "That's really an amazing context.",
    ]
    fake_llm.chat.completions.create = stream
    streamed_gen = gaq.stream(query, context)
    try:
        partial_text = ""
        while True:
            partial_text += next(streamed_gen)
    except StopIteration as err:
        finish_reason = err.value
    assert partial_text == f"I am a great answer. {SOURCES_SEPARATOR}\n 0, 1"
    assert finish_reason == "stop"


@pytest.mark.asyncio
async def test_astream():
    fake_llm = AsyncMock(spec=AsyncOpenAI(api_key="assdas"))
    gaq = GenerativeQAWithSources(client=fake_llm, model="gpt-ni.colas-turbo")
    query = "How nice is this context ?"
    context = [
        "This context is very nice.",
        "I really enjoyed this context.",
        "That's really an amazing context.",
    ]
    fake_create = AsyncMock()
    fake_create.return_value = astream()
    fake_llm.chat.completions.create = fake_create
    try:
        partial_text = ""
        async for word in gaq.astream(query, context):
            partial_text += word
    except RuntimeError as err:
        finish_reason = err.args[0]
    assert partial_text == f"I am a great answer. {SOURCES_SEPARATOR}\n 0, 1"
    assert finish_reason == "stop"


@pytest.mark.parametrize(
    "raw_input, expected_answer, expected_paragraphs",
    [
        (f"Very nice.\n{SOURCES_SEPARATOR.upper()}: 0,1", "Very nice.", [0, 1]),
        (f"Very nice.{SOURCES_SEPARATOR.upper()}: 0,1", "Very nice.", [0, 1]),
        (f"Very nice.{SOURCES_SEPARATOR.lower()}: 0,1", "Very nice.", [0, 1]),
        (f"Very nice.\n{SOURCES_SEPARATOR.lower()}: 0,1", "Very nice.", [0, 1]),
        ("Wrongly formatted input.", None, None),
    ],
)
def test_process_raw_output(raw_input, expected_answer, expected_paragraphs):
    gaq = GenerativeQAWithSources(client=OpenAI(api_key="asaas"))
    res = gaq._process_raw_output(raw_input)
    assert res["answer"] == expected_answer
    assert res["paragraphs"] == expected_paragraphs
