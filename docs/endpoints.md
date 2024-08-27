# Endpoints

## Question Answering

### QA Service Overview

The QA service performs the following steps to generate answers:

1. **Retrieval**: The service retrieves relevant documents and contexts from the database using Elasticsearch (ES) or
   OpenSearch (OS) with BM25. This step provides the initial set of information for generating answers.

2. **Reranker (Optional)**:The reranker takes a large number of retrieved paragraphs and employs a machine learning
   model to re-sort the paragraphs based on semantic similarity to the user's question embedding. It returns the '
   reranker_k' most similar paragraphs, refining the search results.
3. **Answer Generation**: The QA service generates answers using the retrieved documents and the user's question. It
   uses a LLM generative model to compose responses based on the retrieved contexts.

``` mermaid
sequenceDiagram
  autonumber
  SDK->>DocumentStore: Retrieve semantically similar contexts
  SDK->>Reranker: Rerank contexts
  SDK->>DocumentStore: Retrieve document metadata
  SDK->>OpenAI: Ask question from LLM
```

### Calling the endpoint

=== "cURL"

    ``` bash
    curl --location 'https://ml.bbs.master.kcp.bbp.epfl.ch/qa/generative' \
    --header 'Content-Type: application/json' \
    --data '{
        "query": "What is the number of cells in the human brain?",
        "retriever_k": 5,
        "reranker_k": 4,
        "use_reranker": true
    }'
    ```

=== "Python"

    ``` Python
    import requests
    import json

    url = "https://ml.bbs.master.kcp.bbp.epfl.ch/qa/generative"

    payload = json.dumps({
        "query": "What is the number of cells in the human brain?",
        "retriever_k": 5,
        "reranker_k": 4,
        "use_reranker": True
    })
    headers = {
      'Content-Type': 'application/json'
    }

    response = requests.request("POST", url, headers=headers, data=payload)

    print(response.text)
    ```

| Parameter       | Description                                                                                                        |
|-----------------|--------------------------------------------------------------------------------------------------------------------|
| `query`         | The question we want to ask.                                                                                       |
| `retriever_k`   | The number of contexts to retrieve.                                                                                |
| `reranker_k`    | If **use_reranker** is true, we only retrieve the **reranker_k** best contexts.                                    |
| `use_reranker`  | If set to true, we use a ML model to re-sort the retrieved contexts according to semantic similarity to the query. |

### Response Format

The response format of the QA endpoint includes a final answer along with metadata about relevant sources. This
structured format ensures that users receive comprehensive answers.

```json
{
  "answer": "The number of cells in the human brain is approximately 86 billion.",
  "raw_answer": "The number of cells in the human brain is approximately 86 billion.\n<bbs_sources>: 0, 1",
  "metadata": [
    {
      "article_title": "Development and Evolution of the Human Neocortex",
      "article_authors": [
        "Jan H. Lui",
        "David V. Hansen",
        "Arnold R. Kriegstein"
      ],
      "article_id": "e80c88ab244eb08290e6fded98d5b8e2",
      "article_doi": "10.1016/j.cell.2011.06.030",
      "pubmed_id": "21729779",
      "date": "2017-03-01",
      "article_type": "research-article",
      "journal_issn": "0092-8674",
      "journal_name": "Cell (Cambridge)",
      "cited_by": 1097,
      "impact_factor": 1.0,
      "abstract": "The size and surface area of the mammalian brain are thought to be critical determinants of intellectual ability. Recent studies show that development of the gyrated human neocortex involves a lineage of neural stem and transit-amplifying cells that forms the outer subventricular zone (OSVZ), a proliferative region outside the ventricular epithelium. We discuss how proliferation of cells within the OSVZ expands the neocortex by increasing neuron number and modifying the trajectory of migrating neurons. Relating these features to other mammalian species and known molecular regulators of the mouse neocortex suggests how this developmental process could have emerged in evolution.",
      "paragraph": "Studies of the human brain and comparisons of developmental proliferative zones between species may ultimately help to explain what makes the human brain unique. It is commonly thought that the exceptional cognitive abilities of humans are related to the large size of the neocortex. Recent evidence has shown that primates have greater neuronal density (neuron number/brain mass) compared to rodents of equal brain mass, a feature that is likely related to the topological differences in foldedness that could have been influenced by OSVZ proliferation. However, though the human brain is large by weight (1.5 kg) and neuron number (86 billion) (Azevedo et al., 2009; reviewed by Herculano-Houzel, 2009), this ratio does not deviate from what would be expected from a primate brain of similar mass, implying that, in terms of brain size and density, the human brain conforms to a scaled-up primate brain. Furthermore, developmental similarities between the human and ferret show that increased OSVZ proliferation and oRG cells are not primate-specific features (Figure 7A). The percentage of progenitor cells in the SVZ/OSVZ of rodents, carnivores, ungulates, and primates shows a remarkable positive correlation with the degree of neocortical gyrification (Reillo et al., 2010). Thus, development of OSVZ proliferation appears to be an important general feature for increasing neuronal number and neocortical surface area throughout Eutheria.",
      "paragraph_id": "9bb53ebb0f82d2a848c7ef5c1a434293",
      "context_id": 0,
      "reranking_score": null,
      "section": "The Human Neocortex: A Scaled-up Primate Brain"
    }
  ]
}
```

#### Return format properties

| Parameter    | Description                                                                                                                                                  |
|--------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `answer`     | The actual answer to the question.                                                                                                                           |
| `raw_answer` | This is the raw text returned by the Large Language Model. If the pipeline successfully found an answer this will contain  it, as well as a list of sources. |
| `metadata`   | A list where the elements are objects containing key-value pairs. Each objects has metadata about one of the source paragraphs that was retreived.<br/>      |

#### Metadata properties

| Metadata parameter | Description                                                                                    |
|--------------------|------------------------------------------------------------------------------------------------|
| `article_title`    | Title of this article.                                                                         |
| `article_authors`  | A list of authors.                                                                             |
| `article_id`       | Unique identifier of this article in our database.                                             |
| `article_doi`      | Digital Object Identifier of this article.                                                     |
| `pubmed_id`        | A unique identifier used in the PubMed database.                                               |
| `date`             | Publication date of this article.                                                              |
| `article_type`     | The type of scholarly article. Some valid types are: **research, publication, review, thesis** |
| `journal_issn`     | The **International Standard Serial Number** is a unique identifier for journals.              |
| `journal_name`     | The name of the journal where this article was published.                                      |
| `cited_by`         | The number of citations for this article.                                                      |
| `impact_factor`    | The impact factor of the journal where this article was published.                             |
| `abstract`         | The text of the abstract for this article.                                                     |
| `paragraph`        | The actual text of this paragraph.                                                             |
| `paragraph_id`     | The unique identifier of this paragraph in our database.                                       |
| `context_id`       | The unique index of this paragraph that is referenced in the returned answers.                 |
| `reranking_score`  | Score returned by the reranker used to sort contexts by relevance.                             |
| `section`          | Name of the section inside the publication where this paragraphs is from.                      |

### Separators

The QA endpoint uses the following separators within its prompt template:

- **Sources Separator (`SOURCES_SEPARATOR`)**: This placeholder is used to indicate where references to sources should
  be inserted in the final answer. It ensures that users can access the sources related to the provided answer.

- **Error Separator (`ERROR_SEPARATOR`)**: The error separator is used to signify that an answer is not available. When
  an answer is not found, the response starts with the error separator, providing transparency about the absence of a
  valid response.

## Retrieval

One can also retrieve data from the database without the call to a Large Language Model. 

## Article count

The article count endpoint is a convenient endpoint that returns the number of articles in our DB that match certain filters that the user can specify. The filters are described in the [Filtering section](endpoints.md#filtering).

### Calling the endpoint

=== "cURL"

    ``` bash
    curl --location 'https://ml.bbs.master.kcp.bbp.epfl.ch/retrieval/article_count?topics=pyramidal%20cells'
    ```

=== "Python"

    ``` Python
    import requests
    import json

    url = "https://ml.bbs.master.kcp.bbp.epfl.ch/retrieval/article_count?topics=pyramidal%20cells"

    response = requests.request("GET", url)
    ```

### Response Format

The response format of the `article_count` endpoint is a very simple JSON.
```json
{"article_count": 29203}
```


## Article listing

The `article_listing` endpoint is complementary to the `article_count` one. The articles counted in `article_count` can be displayed using this endpoint, granted that the same [filters](endpoints.md#filtering) are applied.

### Calling the endpoint

=== "cURL"

    ``` bash
    curl --location 'https://ml.bbs.master.kcp.bbp.epfl.ch/retrieval/article_listing?topics=pyramidal%20cells'
    ```

=== "Python"

    ``` Python
    import requests
    import json

    url = "https://ml.bbs.master.kcp.bbp.epfl.ch/retrieval/article_listing?topics=pyramidal%20cells"

    response = requests.request("GET", url)
    ```

| Parameter       | Description                                                                                                        |
|-----------------|--------------------------------------------------------------------------------------------------------------------|
| `filters`       | Typical retrieval [filters](endpoints.md#filtering).                                                               |
| `number_results`| Maximum number of unique articles to retrieve from the DB per request.                                             |
| `size`          | Number of unique articles per page.                                                                                |
| `page`          | Page number to retrieve                                                                                            |

!!! note
    The pagination is not a real pagination. For each request, our DB returns `number_results` unique articles, that we split in `ceil(number_results / size)` pages. Specifying a page number or a size such that `page * size > number_results` will result in an empty or partially empty output.

!!! note
    Considering the way we paginate results, each new page retrieved fetches `number_results` articles from our DB and fetches the relevant metadata, leading to a potential heavy load on the DB. For that reason, and at least while we are hosting our DB on kubernetes, `number_results` cannot be too high to avoid crashes.


### Response Format

The response format of the `article_count` endpoint is shown as a JSON containing the relevant metadata about the selected articles.

```json
{
  "items": [
    {
      "article_title": "Suppression of Neuronal Firing Following Antidromic High-Frequency Stimulations on the Neuronal Axons in Rat Hippocampal CA1 Region",
      "article_authors": [
        "Yue Yuan",
        "Zhouyan Feng",
        "Gangsheng Yang",
        "Xiangyu Ye",
        "Zhaoxiang Wang"
      ],
      "article_id": "6d0b455cbdbf594fcf1c22228f9671df",
      "article_doi": "10.3389/fnins.2022.881426",
      "pubmed_id": null,
      "date": "2022-06-10",
      "article_type": "research-article",
      "journal_issn": "1662-4548",
      "journal_name": "Frontiers in neuroscience (Print)",
      "cited_by": 0,
      "impact_factor": null,
      "abstract": "High-frequency stimulation (HFS) of electrical pulses has been used to treat certain neurological diseases in brain with commonly utilized effects within stimulation periods. Post-stimulation effects after the end of HFS may also have functions but are lack of attention. To investigate the post-stimulation effects of HFS, we performed experiments in the rat hippocampal CA1 region in vivo. Sequences of 1-min antidromic-HFS (A-HFS) were applied at the alveus fibers. To evaluate the excitability of the neurons, separated orthodromic-tests (O-test) of paired pulses were applied at the Schaffer collaterals in the period of baseline, during late period of A-HFS, and following A-HFS. The evoked potentials of A-HFS pulses and O-test pulses were recorded at the stratum pyramidale and the stratum radiatum of CA1 region by an electrode array. The results showed that the antidromic population spikes (APS) evoked by the A-HFS pulses persisted through the entire 1-min period of 100 Hz A-HFS, though the APS amplitudes decreased significantly from the initial value of 9.9 ± 3.3 mV to the end value of 1.6 ± 0.60 mV. However, following the cessation of A-HFS, a silent period without neuronal firing appeared before the firing gradually recovered to the baseline level. The mean lengths of both silent period and recovery period of pyramidal cells (21.9 ± 22.9 and 172.8 ± 91.6 s) were significantly longer than those of interneurons (11.2 ± 8.9 and 45.6 ± 35.9 s). Furthermore, the orthodromic population spikes (OPS) and the field excitatory postsynaptic potentials (fEPSP) evoked by O-tests at ∼15 s following A-HFS decreased significantly, indicating the excitability of pyramidal cells decreased. In addition, when the pulse frequency of A-HFS was increased to 200, 400, and 800 Hz, the suppression of neuronal activity following A-HFS decreased rather than increased. These results indicated that the neurons with axons directly under HFS can generate a post-stimulation suppression of their excitability that may be due to an antidromic invasion of axonal A-HFS to somata and dendrites. The finding provides new clues to utilize post-stimulation effects generated in the intervals to design intermittent stimulations, such as closed-loop or adaptive stimulations."
    }
  ],
  "total": 100,
  "page": 1,
  "size": 1,
  "pages": 100
}
```
The meaning of each fields can be found [here](endpoints.md#metadata-properties)
## Journal suggestion

TODO

## Author suggestion

TODO

## Filtering

Many endpoints related to document retrieval from the database share the same set of query parameters that can help further filtering the result of the retrieval. These query parameters are optional and should usually be proposed to the end user to filter his search. This section describes them in details.

### topics

Indicates which topic(s) the article should be about. You can specify multiple topics using the format `topics=xxx&topics=yyy`. If multiple topics are specified, they are **AND** matched. If a topic consists of multiple words, each word is **AND** matched. For instance, specifying `topics=[neuron morphology, electrophysiololgy]` results in the query :

```python
{"query": "((neuron AND morphology) AND electrophysiololgy)"}
```

and only paragraphs containing the words "neuron" **AND** "morpholgy" **AND** "electrophysiology" will be returned.

!!! note
    "neuron morphology" doesn't necessarily have to be present as a whole, each word can be scattered around. For endpoints dealing with articles instead of paragraphs, an article will be returned if at least one of its paragraphs matches the filter.

### regions

Indicates which region(s) (of the brain) the article should be about. You can specify multiple regions using the format `regions=xxx&regions=yyy`. If multiple regions are specified, they are **OR** matched. If a region consists of multiple words, each word is **AND** matched. For instance, specifying `regions=[frontal lobe, isocortex]` results in the query:

```python
{"query": "((frontal AND lobe) OR isocortex)"}
```

and only paragraphs containing the words "frontal + lobe" **OR** "isocortex" will be returned.

!!! note
    "frontal lobe" doesn't necessarily have to be present as a whole, each word can be scattered around. For endpoints dealing with articles instead of paragraphs, an article will be returned if at least one of its paragraphs matches the filter.

!!! note
    If topics and regions are used together, they are **AND** matched. for instance, specifying `topics=[neuron morphology, electrophysiololgy]` and `regions=[frontal lobe, isocortex]` results in the query
    ```python
    {"query": "((neuron AND morphology) AND electrophysiololgy) AND ((frontal AND lobe) OR isocortex)"}
    ```

### article_types

Specifies the type(s) of article that one is looking for. Article types and their occurence are listed by the `/suggestions/article_types` endpoints, which can be used to suggests results for this filter. Examples of article types could be `research-article` or `review-article` for instance. Multiple article types can be specified using the syntax `article_types=xxx&article_types=yyy`.

!!! note
    If multiple article types are specified, they are **OR** matched (i.e. the article should be of type `xxx` **OR** `yyy` **OR**...).

### authors

Specifies which author(s) should have written the article. The endpoint `/suggestions/author` is made available to suggest authors based on partial name matching to help the user fill this filter. Multiple authors can be specified using the syntax `authors=xxx&authors=yyy`.

!!! note
    If multiple authors are specified, they are **OR** matched (i.e. the article should have been written by `xxx` **OR** `yyy` **OR**...).

### journals

Specifies in which journal(s) the article should be published. This query parameter expects the ISSN of the journal in the format `XXXX-XXXX`, not its name. The endpoint `/suggestions/journal` is made available to suggest journals based on name partial matching to help the user fill this filter. Multiple journals can be specified using the syntax `journals=xxx&journals=yyy`.

!!! note
    If multiple journals are specified, they are **OR** matched (i.e. the article should have been published in `XXXX-XXXX` **OR** `YYYY-YYYY` **OR**...).


### date_from

Lower bound on the publication date of the article. Format: `YYYY-MM-DD`

### date_to

Upper bound on the publication date of the article. Format: `YYYY-MM-DD`
