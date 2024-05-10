import torch as t
from tqdm import tqdm
from typing import Dict, List, Union
from torch.utils.data import DataLoader
from utils import entropy
from models import Transformer, Low_rank


device = 'cpu' #mps is way slower!


def compute_loss(model: Union[Transformer, Low_rank], batch: t.Tensor, ent: t.Tensor, loss_fn, next_token: bool) -> t.Tensor:
    """
    Computes the loss of the model on a batch, and adds the entropy for normalization.
    If next_token=True, the predictions are compared with the next token.
    Otherwise, the predictions are compared with the full probability from pi.
    """

    batch = batch.to(device)
    model_logits = model(batch)[0]
    model_proba = t.softmax(model_logits, dim=-1)
    pred_proba = model_proba[:, 1:-1, :]+1e-12

    if next_token:
        target = batch[:, 2:]
        loss = - ent + loss_fn(t.log(pred_proba.flatten(0, 1)), target.flatten(0, 1))
    else:
        true_proba = model.pi[2][batch[:, :-2], batch[:, 1:-1]].detach()
        loss = - ent - (true_proba*t.log(pred_proba)).sum(-1).mean()
    del batch
    return loss


def compute_acc(model: Union[Transformer, Low_rank], batch: t.Tensor) -> t.Tensor:
    """
    Compute the accuracy of the model for predicting the correct token.
    Meaningfull only if the task is to learn a look-up table, low-entropy distribution.
    """
    with t.no_grad():
        model_logits = model(batch)[0]
        predictions = t.argmax(model_logits, dim=-1)
        target = batch[:, 2:]
        acc = (predictions == target).to(t.float).mean()
    return acc


def train(model: Union[Transformer, Low_rank], dataloader: DataLoader, lr: float=1e-3, next_token: bool=True, seed: int=0) -> Dict[str, List[float]]:
    """
    Trains the model and return the loss over all batch.
    """
    
    t.manual_seed(seed)
    model.to(device)
    optimizer = t.optim.Adam(model.parameters(), lr=lr)

    ent = entropy(model.pi).to(device)
    loss_fn = t.nn.CrossEntropyLoss()

    Loss = []
    Acc = []
    for batch in tqdm(dataloader):
        loss = compute_loss(model, batch[0], ent, loss_fn, next_token)
        acc = compute_acc(model, batch[0]) #incorrect
        loss.backward()
        optimizer.step()
        optimizer.zero_grad()
        
        Loss.append(loss.item())
        Acc.append(acc.item())
    model.to('cpu')
    
    return {'Loss': Loss, 'Acc': Acc}