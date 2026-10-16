"""Create a tiny random BERT + tokenizer + two adapters on disk, so the dense code paths
(E5 mean pooling, SPECTER2 adapters, caching, exact search) can be tested without
downloading anything. The numbers these produce are meaningless."""
import sys
from pathlib import Path

out = Path(sys.argv[1])
corpus = sys.argv[2]
out.mkdir(parents=True, exist_ok=True)

from tokenizers import BertWordPieceTokenizer
import json
texts = []
for line in open(corpus):
    d = json.loads(line)
    texts.append(d.get("title", "") + " " + d.get("text", d.get("abstract", "")))
tmp = out / "texts.txt"
tmp.write_text("\n".join(texts[:3000]))
tok = BertWordPieceTokenizer(lowercase=True)
tok.train([str(tmp)], vocab_size=3000, min_frequency=2)
(out / "base").mkdir(exist_ok=True)
tok.save_model(str(out / "base"))

from transformers import BertConfig, BertModel, BertTokenizerFast
t = BertTokenizerFast(vocab_file=str(out / "base" / "vocab.txt"), do_lower_case=True)
t.save_pretrained(out / "base")
cfg = BertConfig(vocab_size=t.vocab_size, hidden_size=64, num_hidden_layers=2, num_attention_heads=2,
                 intermediate_size=128, max_position_embeddings=512)
BertModel(cfg).save_pretrained(out / "base")

from adapters import AutoAdapterModel, SeqBnConfig
m = AutoAdapterModel.from_pretrained(out / "base")
for name in ("proximity", "adhoc_query"):
    m.add_adapter(name, config=SeqBnConfig())
    m.save_adapter(str(out / name), name)
print("tiny models in", out)
