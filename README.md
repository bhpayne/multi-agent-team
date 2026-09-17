
# About

While the intent is to have multiple concurrent agents, currently the orchestration is just sequential calls to an LLM by a serial Python script. 

Sandboxed using Docker

# Use/quickstart

Launch local LLM API:
```
python3 -m llama_cpp.server --model ./models/gemma-4-E4B-it-qat-UD-Q4_K_XL.gguf --n_gpu_layers -1  --n_ctx 16384
```
Create the container:
```
make
```
Run the orchestration inside the container
```
python3 run_prompts.py 
```

# useful sites

https://jsonlint.com/json-schema-generator
https://jsonlint.com/


# TODO


max token count determines memory usage

sending a Markdown file (1 page) of input and asking for additions is over the default max token count of 2048

--> Could dynamically alter the max token count if the "finish_reason" is "length" rather than "stop"