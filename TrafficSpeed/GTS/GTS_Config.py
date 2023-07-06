import argparse
import configparser

MODE = 'test'
DEBUG = True
DEVICE = 'cuda:5'
MODEL = 'GTS'
DATASET = 'PEMSBAY'  # PEMSBAY
dataset_dir = "../data/PEMS-BAY/processed/"
origin_data = "../data/PEMS-BAY/pems-bay.h5"
graph_pkl = "../data/PEMS-BAY/processed/adj_mx.pkl"

# 1. get configuration
config_file = './{}_{}.conf'.format(DATASET, MODEL)
config = configparser.ConfigParser()
config.read(config_file)

# 2. arguments parser
args = argparse.ArgumentParser(description='Arguments')
args.add_argument('--mode', default=MODE, type=str)
args.add_argument('--debug', default=DEBUG, type=eval)
args.add_argument('--device', default=DEVICE, type=str)
args.add_argument('--model', default=MODEL, type=str)
args.add_argument('--dataset', default=DATASET, type=str)
args.add_argument('--dataset_dir', default=dataset_dir, type=str)
args.add_argument('--origin_data', default=origin_data, type=str)
args.add_argument('--graph_pkl', default=graph_pkl, type=str)
args.add_argument('--num_nodes', default=config['data']['num_nodes'], type=int)
args.add_argument('--window', default=config['data']['window'], type=int)
args.add_argument('--horizon', default=config['data']['horizon'], type=int)

# 3. model params
args.add_argument('--input_dim', default=config['model']['input_dim'], type=eval)
args.add_argument('--output_dim', default=config['model']['output_dim'], type=eval)
args.add_argument('--rnn_units', default=config['model']['rnn_units'], type=eval)
args.add_argument('--num_rnn_layers', default=config['model']['num_rnn_layers'], type=eval)
args.add_argument('--filter_type', default=config['model']['filter_type'], type=eval)
args.add_argument('--cl_decay_steps', default=config['model']['cl_decay_steps'], type=eval)
args.add_argument('--max_diffusion_step', default=config['model']['max_diffusion_step'], type=eval)
args.add_argument('--use_curriculum_learning', default=config['model']['use_curriculum_learning'], type=eval)
args.add_argument('--dim_fc', default=config['model']['dim_fc'], type=eval)
args.add_argument('--l1_decay', default=config['model']['l1_decay'], type=eval)
args.add_argument('--temperature', default=config['model']['temperature'], type=eval)

# 4. train params
args.add_argument('--cl', default=config['train']['cl'], type=eval)
args.add_argument('--seed', default=config['train']['seed'], type=int)
args.add_argument('--knn_k', default=config['train']['knn_k'], type=int)
args.add_argument('--loss_func', default=config['train']['loss_func'], type=str)
args.add_argument('--batch_size', default=config['train']['batch_size'], type=int)
args.add_argument('--epochs', default=config['train']['epochs'], type=int)
args.add_argument('--weight_decay', default=config['train']['weight_decay'], type=float)
args.add_argument('--epsilon', default=config['train']['epsilon'], type=float)
args.add_argument('--lr_init', default=config['train']['lr_init'], type=float)
args.add_argument('--lr_decay', default=config['train']['lr_decay'], type=eval)
args.add_argument('--lr_decay_rate', default=config['train']['lr_decay_rate'], type=float)
args.add_argument('--lr_decay_step', default=config['train']['lr_decay_step'], type=str)
args.add_argument('--early_stop', default=config['train']['early_stop'], type=eval)
args.add_argument('--early_stop_patience', default=config['train']['early_stop_patience'], type=int)
args.add_argument('--grad_norm', default=config['train']['grad_norm'], type=eval)
args.add_argument('--max_grad_norm', default=config['train']['max_grad_norm'], type=int)
args.add_argument('--step_size', default=config['train']['step_size'], type=int)
args.add_argument('--new_training_method', default=config['train']['new_training_method'], type=eval)
args.add_argument('--epoch_use_regularization', default=config['train']['epoch_use_regularization'], type=eval)
args = args.parse_args()