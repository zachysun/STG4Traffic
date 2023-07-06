import sys
sys.path.append('../')

import os
import copy
import time
import torch
from lib.utils import *

class Trainer(object):
    def __init__(self, args, data_loader, scaler, model, loss, optimizer, lr_scheduler, node_feas, adj_mx, cl=True):
        super(Trainer, self).__init__()
        self.args = args
        self.data_loader = data_loader
        self.train_loader = data_loader['train_loader']
        self.val_loader = data_loader['val_loader']
        self.test_loader = data_loader['test_loader']
        self.scaler = scaler
        # model, loss_func, optimizer, lr_scheduler
        self.model = model
        self.loss = loss
        self.optimizer = optimizer
        self.lr_scheduler = lr_scheduler
        # 日志与模型的保存路径
        self.best_path = os.path.join(args.log_dir, '{}_{}_best_model.pth'.format(args.dataset, args.model))
        if os.path.isdir(args.log_dir) == False and not args.debug:
            os.makedirs(args.log_dir, exist_ok=True)  # run.log
        self.logger = get_logger(args.log_dir, name=args.model, debug=args.debug)
        self.logger.info("Experiment log path in: {}".format(args.log_dir))
        self.logger.info(args)

        self.node_feas = node_feas
        self.adj_mx = adj_mx
        self.temperature = args.temperature
        self.gumbel_soft = True
        self.cl = cl
        self.horizon = args.horizon
        self.batches_seen = 0


    def train_epoch(self, epoch_num):
        train_loss = []
        train_rmse = []
        train_mape = []
        if epoch_num < self.args.epoch_use_regularization:
            label = 'with_regularization'
        else:
            label = 'without_regularization'
        self.model.train()
        self.train_loader.shuffle()
        for _, (x, y, ycl) in enumerate(self.train_loader.get_iterator()):
            trainx = torch.Tensor(x).to(self.args.device)
            trainy = torch.Tensor(y)[:, :, :, 0:1].to(self.args.device)
            trainycl = torch.Tensor(ycl)[:, :, :, 0:1].to(self.args.device)
            self.optimizer.zero_grad()
            if self.cl:
                # curriculum learning  (B, T, N, 1)
                trainx = trainx.transpose(0, 1).reshape(self.args.horizon, self.args.batch_size, -1)     # (T, B, 1 * N)
                trainy = trainy.transpose(0, 1).reshape(self.args.horizon, self.args.batch_size, -1)     # (T, B, 1 * N)
                trainycl = trainycl.transpose(0, 1).reshape(self.args.horizon, self.args.batch_size, -1)

                # (T, B, 1 * N)
                output, mid_output = self.model(label, trainx, self.node_feas, self.temperature, self.gumbel_soft, trainycl, batches_seen=self.batches_seen)
                if self.batches_seen == 0:
                    self.optimizer = torch.optim.Adam(self.model.parameters(), lr=self.args.lr_init, eps=self.args.epsilon)
                # 预测的是归一化的结果, 所以需要反归一化
                predict = self.scaler.inverse_transform(output)
                if label == 'without_regularization':
                    loss = self.loss(predict, trainy, 0.0)
                else:
                    loss_1 = self.loss(predict, trainy, 0.0)
                    pred = mid_output.view(mid_output.shape[0] * mid_output.shape[1])
                    true_label = self.adj_mx.view(mid_output.shape[0] * mid_output.shape[1]).to(self.args.device)
                    compute_loss = torch.nn.BCELoss()
                    loss_g = compute_loss(pred, true_label)
                    loss = loss_1 + loss_g
                mape = masked_mape(predict, trainy, 0.0).item()
                rmse = masked_rmse(predict, trainy, 0.0).item()
            else:
                output = self.model(trainx)
                # 预测的是归一化的结果, 所以需要反归一化
                predict = self.scaler.inverse_transform(output)
                loss = self.loss(predict, trainy[:, :, :, 0:1], 0.0)
                mape = masked_mape(predict, trainy[:, :, :, 0:1], 0.0).item()
                rmse = masked_rmse(predict, trainy[:, :, :, 0:1], 0.0).item()                
            self.batches_seen += 1
            loss.backward()

            if self.args.grad_norm:
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.args.max_grad_norm)
            self.optimizer.step()
        
            train_loss.append(loss.item())
            train_mape.append(mape)
            train_rmse.append(rmse)
        mtrain_loss = np.mean(train_loss)
        mtrain_mape = np.mean(train_mape)
        mtrain_rmse = np.mean(train_rmse)
        return mtrain_loss, mtrain_rmse, mtrain_mape


    def val_epoch(self, epoch_num):
        valid_loss = []
        valid_mape = []
        valid_rmse = []

        if epoch_num < self.args.epoch_use_regularization:
            label = 'with_regularization'
        else:
            label = 'without_regularization'
        self.model.eval()
        with torch.no_grad():
            for _, (x, y) in enumerate(self.val_loader.get_iterator()):
                validx = torch.Tensor(x).to(self.args.device)
                validy = torch.Tensor(y)[:, :, :, 0:1].to(self.args.device)
                if self.cl:
                    validx = validx.transpose(0, 1).reshape(self.args.horizon, self.args.batch_size, -1)  # (T, B, 1*N)
                    validy = validy.transpose(0, 1).reshape(self.args.horizon, self.args.batch_size, -1)  # (T, B, 1*N)
                    output, mid_output = self.model(label, validx, self.node_feas, self.temperature, self.gumbel_soft)  # (T, B, N*1)
                    predict = self.scaler.inverse_transform(output)
                    if label == 'without_regularization':
                        loss = self.loss(predict, validy, 0.0)
                    else:
                        loss_1 = self.loss(predict, validy, 0.0)
                        pred = mid_output.view(mid_output.shape[0] * mid_output.shape[1])
                        true_label = self.adj_mx.view(mid_output.shape[0] * mid_output.shape[1]).to(self.args.device)
                        compute_loss = torch.nn.BCELoss()
                        loss_g = compute_loss(pred, true_label)
                        loss = loss_1 + loss_g
                    mape = masked_mape(predict, validy, 0.0).item()
                    rmse = masked_rmse(predict, validy, 0.0).item()
                else:
                    output = self.model(validx)  # (B, T, N, 1)
                    # 预测的是归一化的结果, 所以需要反归一化
                    predict = self.scaler.inverse_transform(output)
                    loss = self.loss(predict, validy[:, :, :, 0:1], 0.0)
                    mape = masked_mape(predict, validy[:, :, :, 0:1], 0.0).item()
                    rmse = masked_rmse(predict, validy[:, :, :, 0:1], 0.0).item()  
                valid_loss.append(loss.item())
                valid_rmse.append(rmse)
                valid_mape.append(mape)
        
        mvalid_loss = np.mean(valid_loss)
        mvalid_mape = np.mean(valid_mape)
        mvalid_rmse = np.mean(valid_rmse)
        return mvalid_loss, mvalid_rmse, mvalid_mape


    def train(self):
        self.logger.info("start training...")
        best_model = None
        best_loss = float('inf')
        not_improved_count = 0
        train_loss_list = []
        val_loss_list = []
        start_time = time.time()
        for epoch in range(1, self.args.epochs + 1):
            t1 = time.time()
            mtrain_loss, _, _ = self.train_epoch(epoch)
            t2 = time.time()
            if self.args.lr_decay:
                self.lr_scheduler.step()
            mvalid_loss, mvalid_rmse, mvalid_mape = self.val_epoch(epoch)
            t3 = time.time()
            self.logger.info('Epoch {:03d}, Train Loss: {:.4f}, Valid Loss: {:.4f}, Valid RMSE: {:.4f}, Valid MAPE: {:.4f}, Training Time: {:.4f} secs, Inference Time: {:.4f} secs.'.format(epoch, mtrain_loss, mvalid_loss, mvalid_rmse, mvalid_mape, (t2 - t1), (t3 - t2)))
            train_loss_list.append(mtrain_loss)
            val_loss_list.append(mvalid_loss)
            if mtrain_loss > 1e6:
                self.logger.warning("Gradient explosion detected. Ending...")
                break
            if mvalid_loss < best_loss:
                best_loss = mvalid_loss
                not_improved_count = 0
                best_state = True
            else:
                not_improved_count += 1
                best_state = False
            
            # early stop is or not
            if self.args.early_stop:
                if not_improved_count == self.args.early_stop_patience:
                    self.logger.info("Validation performance didn\'t improve for {} epochs. "
                                    "Training stops.".format(self.args.early_stop_patience))
                    break
            # save the best model
            if best_state == True:
                # self.logger.info("Current best model saved!")
                best_model = copy.deepcopy(self.model.state_dict())
                torch.save(best_model, self.best_path)

        training_time = time.time() - start_time
        self.logger.info("Total training time: {:.4f} min, best loss: {:.6f}".format((training_time / 60), best_loss))
        # save the best model to file
        self.logger.info("Saving current best model to " + self.best_path)
        # Let's test the model
        self.model.load_state_dict(best_model)
        self.test(self.args, self.model, self.data_loader, self.scaler, self.logger)

    def setup_graph(self):
        self.model.eval()
        with torch.no_grad():
            for _, (x, y) in enumerate(self.val_loader.get_iterator()):
                validx = torch.Tensor(x).to(self.args.device)
                validy = torch.Tensor(y)[:, :, :, 0:1].to(self.args.device)
                if self.cl:
                    # label='without_regularization', inputs=testx, node_feas=self.node_feas, temp=0.5, gumbel_soft=True
                    validx = validx.transpose(0, 1).reshape(self.args.horizon, self.args.batch_size, -1)  # (T, B, 1*N)
                    validy = validy.transpose(0, 1).reshape(self.args.horizon, self.args.batch_size, -1)  # (T, B, 1*N)
                    self.model(label='with_regularization', inputs=validx, node_feas=self.node_feas, temp=0.5, gumbel_soft=True)  # (T, B, N*1)
                else:
                    self.model(validx, self.node_feas)  # (B, T, N, 1)
                break
                
    def test(self, args, model, data_loader, scaler, logger, save_path=None):
        if save_path != None:
            self.setup_graph()
            model.load_state_dict(torch.load(save_path))
            model.to(args.device)
            print("load saved model...")
        model.eval()
        outputs = []
        realy = torch.Tensor(data_loader['y_test']).to(args.device)
        realy = realy[:, :, :, 0:1].squeeze()   # (B, T, N)
        realy = realy.transpose(0, 1).reshape(self.args.horizon, -1, args.num_nodes)
        with torch.no_grad():
            for _, (x, y) in enumerate(data_loader['test_loader'].get_iterator()):
                testx = torch.Tensor(x).to(args.device)
                testy = torch.Tensor(y).to(args.device)
                if self.cl:
                    testx = testx.transpose(0, 1).reshape(self.args.horizon, self.args.batch_size, -1)  # (B, 1, N, T)
                    testy = testy.transpose(0, 1).reshape(self.args.horizon, self.args.batch_size, -1)  # (B, 1, N, T)
                    # label, inputs, node_feas, temp, gumbel_soft
                    preds, _ = self.model(label='with_regularization', inputs=testx, node_feas=self.node_feas, temp=0.5, gumbel_soft=True)  # (T, B, 1*N)
                else:
                    preds, _ = self.model(testx)   # (B, T, N, 1)
                outputs.append(preds)
        
        yhat = torch.cat(outputs, dim=1)
        yhat = yhat[:, :realy.size(1), :]   # concat at batch_size
        mae = []
        rmse = []
        mape = []
        for i in range(args.horizon):
            # 预测的是归一化的结果, 所以需要反归一化
            pred = scaler.inverse_transform(yhat[i, :, :])  # (T, B, N)
            real = realy[i, :, :]  # (T, B, N)
            metrics = metric(pred, real)
            log = 'Evaluate model for horizon {:2d}, MAE: {:.4f}, MAPE: {:.4f}, RMSE: {:.4f}'
            logger.info(log.format(i + 1, metrics[0], metrics[1], metrics[2]))
            mae.append(metrics[0])
            mape.append(metrics[1])
            rmse.append(metrics[2])
        logger.info('On average over 12 horizons, MAE: {:.4f}, MAPE: {:.4f}, RMSE: {:.4f}'.format(np.mean(mae), np.mean(mape), np.mean(rmse)))