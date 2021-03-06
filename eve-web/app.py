from starlette.applications import Starlette
from starlette.responses import UJSONResponse
import gpt_2_simple as gpt2
import tensorflow as tf
import uvicorn
import os
import re


MIN_LENGTH = 50
MAX_LENGTH = 200
STEP_LENGTH = 50

VALID_CATEGORIES = {
    'confession',
    'lostlove',
    'missing',
    'secondchance',
    'sorry',
    'thinkingofyou',
    'love'
}

app = Starlette(debug=False)

sess = gpt2.start_tf_sess(threads=1)
gpt2.load_gpt2(
    sess,
    run_name="run1",
    checkpoint_dir="checkpoint"
)

# Needed to avoid cross-domain issues
response_header = {
    'Access-Control-Allow-Origin': '*'
}

generate_count = 0


@app.route('/', methods=['GET', 'POST', 'HEAD'])
async def homepage(request):
    global generate_count
    global sess

    if request.method == 'GET':
        params = request.query_params
    elif request.method == 'POST':
        params = await request.json()
    elif request.method == 'HEAD':
        return UJSONResponse({'text': ''},
                             headers=response_header)

    keywords = " ".join([v.replace(' ', '-').strip() for k, v in params.items()
                         if 'key' in k and v != ''])

    title = params.get('title', '')[:100]
    
    prepend = "<|startoftext|>~^{}~@{}~}}".format(keywords, title)
    text = prepend + params.get('prefix', '')[:100]

    length = MIN_LENGTH

    while '<|endoftext|>' not in text and length <= MAX_LENGTH:
        text = gpt2.generate(sess,
                             run_name="run1",
                             length=STEP_LENGTH,
                             temperature=0.7,
                             top_k=40,
                             prefix=text,
                             include_prefix=True,
                             return_as_list=True
                             )[0]
        length += STEP_LENGTH

        generate_count += 1
        if generate_count == 8:
            # Reload model to prevent Graph/Session from going OOM
            tf.reset_default_graph()
            sess.close()
            sess = gpt2.start_tf_sess(threads=1)
            gpt2.load_gpt2(sess)
            generate_count = 0

    prepend_esc = re.escape(prepend)
    eot_esc = re.escape('<|endoftext|>')
    print(text)

    if '<|endoftext|>' not in text:
        pattern = '(?:{})(.*)'.format(prepend_esc)
    else:
        pattern = '(?:{})(.*)(?:{})'.format(prepend_esc, eot_esc)

    trunc_text = re.search(pattern, text)
    resp_text = trunc_text.group(1) if trunc_text else ""

    return UJSONResponse({'text': resp_text.replace("~}", " ")},
                         headers=response_header)

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
