import torch 
import numpy as np
import torch.nn.functional as F

from src.modules import sstransforms as sst


def compute_cross_entropy(images, logits, masks):
    _, n_classes, _, _ = logits.shape
    if n_classes == 1:
        loss = F.binary_cross_entropy_with_logits(logits, masks.float(), reduction='mean')
    else:
        probs = F.log_softmax(logits, dim=1)
        loss = F.nll_loss(probs, masks.long(), reduction='mean', ignore_index=255)
    return loss 

def compute_focal_cross_entropy(images, logits, masks):
    gamma=3/4
    _, n_classes, _, _ = logits.shape
    if n_classes == 1:
        loss = F.binary_cross_entropy_with_logits(logits, masks.float(), reduction='mean')
    else:
        probs = F.log_softmax(logits, dim=1)
        l = F.nll_loss(probs, masks.long(), reduction='mean', ignore_index=255)
        #p_gamma = torch.pow(l,gamma)
        #_p_gamma = torch.pow(1-l,gamma)
        #loss = _p_gamma/torch.pow(p_gamma+_p_gamma,1/gamma)
        loss = torch.pow(l,gamma)
    return loss

def compute_dice_loss(images, logits, masks, smooth = 1e-10):
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    masks = torch.unsqueeze(masks, 1)
    yTrueOnehot = torch.zeros(masks.size(0), 2, masks.size(2), masks.size(3), device=device) # 2 = num_classes
    yTrueOnehot = torch.scatter(yTrueOnehot, 1, masks, 1)[:, 1:]
    y_pred = F.softmax(logits, dim=1)[:, 1:]
    # yTrueOnehot = torch.scatter(yTrueOnehot, 1, masks, 1)
    # y_pred = F.softmax(logits, dim=1)
    ################### tversky #####################
    TP = torch.sum(yTrueOnehot * y_pred, dim=[1,2,3])
    cardinality  = torch.sum(yTrueOnehot + y_pred, dim=[1,2,3])
    loss = 1-torch.mean((2. * TP + 1e-5) / (cardinality + 1e-5))
    return loss

def compute_tversky_loss(images, logits, masks, smooth = 1e-10):
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    masks = torch.unsqueeze(masks, 1)
    yTrueOnehot = torch.zeros(masks.size(0), 2, masks.size(2), masks.size(3), device=device) # 2 = num_classes
    yTrueOnehot = torch.scatter(yTrueOnehot, 1, masks, 1)[:, 1:]
    y_pred = F.softmax(logits, dim=1)[:, 1:]
    # yTrueOnehot = torch.scatter(yTrueOnehot, 1, masks, 1)
    # y_pred = F.softmax(logits, dim=1)
    ################### tversky #####################
    TP = torch.sum(yTrueOnehot * y_pred, dim=[1,2,3])
    FN = torch.sum(yTrueOnehot * (1-y_pred), dim=[1,2,3])
    FP = torch.sum((1-yTrueOnehot) * y_pred, dim=[1,2,3])
    loss = 1-torch.mean((TP + 1e-5) / (TP + 0.7 * FP + 0.3 * FN + 1e-5))
    return loss
    # TN = torch.sum((1-yTrueOnehot) * (1-y_pred))
    # numerator = torch.sum(yTrueOnehot * y_pred)
    # denominator = masks.size(0) * masks.size(2) * masks.size(3)
    # acc = (TP+TN)/denominator
    # print("TP+TN: ",TP+TN)
    # return 1 - acc
    ############ dice loss #########################################
    # TP = torch.sum(yTrueOnehot * y_pred, dim=[1,2,3])
    # cardinality  = torch.sum(yTrueOnehot + y_pred, dim=[1,2,3])
    # loss = 1-torch.mean((2. * TP + 1e-5) / (cardinality + 1e-5))
    # return loss
    ############### cross entropy loss #################################
    # device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    # masks = torch.unsqueeze(masks, 1)
    # yTrueOnehot = torch.zeros(masks.size(0), 2, masks.size(2), masks.size(3), device=device) # 2 = num_classes
    # yTrueOnehot = torch.scatter(yTrueOnehot, 1, masks, 1)
    # y_pred = F.softmax(logits, dim=1)
    # loss = torch.sum(-yTrueOnehot * torch.log(y_pred+1e-10))
    # return loss / (y_pred.size(0) * y_pred.size(2) * y_pred.size(3))
    

# def compute_accuracy_loss(images, logits, masks):
#     #masks.shape = [1,512,512]
#     print("unique", torch.unique(masks))
#     yTrueOnehot = masks.view(2,-1,512,512)
#     print('yTrueOnehot: ', yTrueOnehot.shape)
#     logits = torch.sigmoid(logits)
#     print('logits: ', logits.shape)

#     TP = torch.sum(yTrueOnehot*logits)
#     print('TP: ', TP)
#     FN = torch.sum(yTrueOnehot*(1-logits))
#     print('FN: ', FN)
#     FP = torch.sum((1-yTrueOnehot)*logits)
#     print('FP: ', FP)
#     TN = torch.sum((1-yTrueOnehot)*(1-logits))
#     print('TN: ', TN)
#     loss = (FP+FN+1e-10)/(TP+TN+FP+FN+1e-10)
#     return loss

def compute_point_level(images, logits, point_list):
    _, n_classes, _, _ = logits.shape
    class_labels = torch.zeros(n_classes).cuda().long()
    class_labels[np.unique([p['cls'] for p in point_list[0]])] = 1
    n,c,h,w = logits.shape
    class_logits = logits.view(n,c,h*w)
    # REGION LOSS
    loss = F.multilabel_soft_margin_loss(class_logits.max(2)[0], class_labels[None], reduction='mean')

    # POINT LOSS
    points = torch.ones(h,w).cuda()*255
    for p in point_list[0]:
        if p['y'] >= h or p['x'] >= w: 
            continue
        points[int(p['y']), int(p['x'])] = p['cls']
    probs = F.log_softmax(logits, dim=1)
    loss += F.nll_loss(probs, points[None].long(), reduction='mean', ignore_index=255)

    return loss

def compute_const_point_mean_loss(model, images, logits, point_list=None):
    from kornia.geometry.transform import flips

    # consistency loss
    logits_flip = model(flips.Hflip()(images))
    loss = torch.mean(torch.abs(flips.Hflip()(logits_flip)-logits))
    
    # point loss
    if point_list is not None:
        loss = loss + compute_point_level(images, logits, point_list)

    return loss 

def compute_const_point_loss(model, images, logits, point_list=None):
    from kornia.geometry.transform import flips

    # consistency loss
    logits_flip = model(flips.Hflip()(images))
    loss = torch.max(torch.abs(flips.Hflip()(logits_flip)-logits))
    
    # point loss
    if point_list is not None:
        loss = loss + compute_point_level(images, logits, point_list)

    return loss 

def compute_rot_point_loss(model, images, logits, point_list):
    from kornia.geometry.transform import flips
    
    # rotation loss
    rotations = np.random.choice([0, 90, 180, 270], images.shape[0], replace=True)
    images = flips.Hflip()(images)
    images_rotated = sst.batch_rotation(images, rotations)
    logits_rotated = model(images_rotated)
    logits_recovered = sst.batch_rotation(logits_rotated, 360 - rotations)
    logits_recovered = flips.Hflip()(logits_recovered)
    
    loss = torch.mean(torch.abs(logits_recovered-logits))
    
    # point loss
    loss += compute_point_level(images, logits, point_list)

    return loss

def compute_other_loss(self, loss_name, images, logits, points, point_list=None):
        if loss_name == 'toponet':
            if self.first_time:
                self.first_time = False
                self.vgg = nn.DataParallel(lanenet.VGG().cuda(1), list(range(1,4)))
                self.vgg.train()
            points = points[:,None]
            images_flip = flips.Hflip()(images)
            logits_flip = self.model_base(images_flip)
            loss = torch.mean(torch.abs(flips.Hflip()(logits_flip)-logits))
            
            logits_flip_vgg = self.vgg(F.sigmoid(logits_flip.cuda(1)))
            logits_vgg = self.vgg(F.sigmoid(logits.cuda(1))) 
            loss += self.exp_dict["model"]["loss_weight"] * torch.mean(torch.abs(flips.Hflip()(logits_flip_vgg)-logits_vgg)).cuda(0)

            ind = points!=255
            if ind.sum() != 0:
                loss += F.binary_cross_entropy_with_logits(logits[ind], 
                                        points[ind].float().cuda(), 
                                        reduction='mean')

                points_flip = flips.Hflip()(points)
                ind = points_flip!=255
                loss += F.binary_cross_entropy_with_logits(logits_flip[ind], 
                                        points_flip[ind].float().cuda(), 
                                        reduction='mean')

        elif loss_name == 'multiscale_cons_point_loss':
            logits, features = logits
            points = points[:,None]
            ind = points!=255
            # self.vis_on_batch(batch, savedir_image='tmp.png')

            # POINT LOSS
            # loss = ut.joint_loss(logits, points[:,None].float().cuda(), ignore_index=255)
            # print(points[ind].sum())
            logits_flip, features_flip = self.model_base(flips.Hflip()(images), return_features=True)

            loss = torch.mean(torch.abs(flips.Hflip()(logits_flip)-logits))
            for f, f_flip in zip(features, features_flip):
                loss += torch.mean(torch.abs(flips.Hflip()(f_flip)-f)) * self.exp_dict["model"]["loss_weight"]
            if ind.sum() != 0:
                loss += F.binary_cross_entropy_with_logits(logits[ind], points[ind].float().cuda(), reduction='mean')

                # logits_flip = self.model_base(flips.Hflip()(images))
                points_flip = flips.Hflip()(points)
                ind = points_flip!=255
                # if 1:
                #     pf = points_flip.clone()
                #     pf[pf==1] = 2
                #     pf[pf==0] = 1
                #     pf[pf==255] = 0
                #     lcfcn_loss.save_tmp('tmp.png', flips.Hflip()(images[[0]]), logits_flip[[0]], 3, pf[[0]])
                loss += F.binary_cross_entropy_with_logits(logits_flip[ind], points_flip[ind].float().cuda(), reduction='mean')

        elif loss_name == "affine_cons_point_loss":
            def rotate_img(self, img, rot):
                if rot == 0:  # 0 degrees rotation
                    return img
                elif rot == 90:  # 90 degrees rotation
                    return np.flipud(np.transpose(img, (1, 0, 2)))
                elif rot == 180:  # 90 degrees rotation
                    return np.fliplr(np.flipud(img))
                elif rot == 270:  # 270 degrees rotation / or -90
                    return np.transpose(np.flipud(img), (1, 0, 2))
                else:
                    raise ValueError('rotation should be 0, 90, 180, or 270 degrees')
            affine_params = self.exp_dict['model']["affine_params"]
            points = points[:,None].float().cuda()
            if np.random.randint(2) == 0:
                images_flip = flips.Hflip()(images)
                flipped = True
            else:
                images_flip = images
                flipped = False
            batch_size, C, height, width = logits.shape
            random_affine = RandomAffine(**affine_params, return_transform=True)
            images_aff, transform = random_affine(images_flip)
            logits_aff = self.model_base(images_aff)
            
            # hu.save_image('tmp1.png', images_aff[0])
            itransform = transform.inverse()
            logits_aff = kornia.geometry.transform.warp_affine(logits_aff, itransform[:,:2, :], dsize=(height, width))
            if flipped:
                logits_aff = flips.Hflip()(logits_aff)
            # hu.save_image('tmp2.png', logits_aff[0])

            
            # logits_flip = self.model_base(flips.Hflip()(images))

            loss = self.exp_dict['model']["loss_weight"] * torch.mean(torch.abs(logits_aff-logits))
            points_aff = kornia.geometry.transform.warp_affine(points, transform[:,:2, :], dsize=(height, width), flags="bilinear")
            # points_aff = points
            ind = points!=255
            if ind.sum() != 0:
                loss += F.binary_cross_entropy_with_logits(logits[ind], 
                                        points[ind], 
                                        reduction='mean')
                if flipped:
                    points_aff = flips.Hflip()(points_aff)
                # logits_flip = self.model_base(flips.Hflip()(images))
                ind = points_aff <= 1
                loss += F.binary_cross_entropy_with_logits(logits_aff[ind], 
                                        points_aff[ind].detach(), 
                                        reduction='mean')
        elif loss_name == "elastic_cons_point_loss":
            points = points[:,None].float().cuda()
            ind = points!=255
            # self.vis_on_batch(batch, savedir_image='tmp.png')

            # POINT LOSS
            # loss = ut.joint_loss(logits, points[:,None].float().cuda(), ignore_index=255)
            # print(points[ind].sum())
            B, C, H, W = images.shape
            # ELASTIC TRANSFORM
            def norm_grid(grid):
                grid -= grid.min()
                grid /= grid.max()
                grid = (grid - 0.5) * 2
                return grid 
            grid_x, grid_y = torch.meshgrid(torch.arange(H), torch.arange(W))
            grid_x = grid_x.float().cuda()
            grid_y = grid_y.float().cuda()
            sigma=self.exp_dict["model"]["sigma"]
            alpha=self.exp_dict["model"]["alpha"]
            indices = torch.stack([grid_y, grid_x], -1).view(1, H, W, 2).expand(B, H, W, 2).contiguous()
            indices = norm_grid(indices)
            dx = gaussian_filter((np.random.rand(H, W) * 2 - 1), sigma, mode="constant", cval=0) * alpha
            dy = gaussian_filter((np.random.rand(H, W) * 2 - 1), sigma, mode="constant", cval=0) * alpha
            dx = torch.from_numpy(dx).cuda().float()
            dy = torch.from_numpy(dy).cuda().float()
            dgrid_x = grid_x + dx
            dgrid_y = grid_y + dy
            dgrid_y = norm_grid(dgrid_y)
            dgrid_x = norm_grid(dgrid_x)
            dindices = torch.stack([dgrid_y, dgrid_x], -1).view(1, H, W, 2).expand(B, H, W, 2).contiguous()
            # dindices0 = dindices.permute(0, 3, 1, 2).contiguous().view(B*2, H, W)
            # indices0 = indices.permute(0, 3, 1, 2).contiguous().view(B*2, H, W)
            # iindices = torch.bmm(indices0, dindices0.pinverse()).view(B, 2, H, W).permute(0, 2, 3, 1)
            # indices_im = indices.permute(0, 3, 1, 2)
            # iindices = F.grid_sample(indices_im, dindices).permute(0, 2, 3, 1)
            images_aug = F.grid_sample(images, dindices)
            logits_aug = self.model_base(images_aug)
            aug_logits = F.grid_sample(logits, dindices)
            points_aug = F.grid_sample(points, dindices, mode='nearest')
            loss = self.exp_dict['model']["loss_weight"] * torch.mean(torch.abs(logits_aug-aug_logits))


            # logits_aff = self.model_base(images_aff)
            # inv_transform = transform.inverse()
            
            import pylab
            def save_im(image, name):
                _images_aff = image.data.cpu().numpy()
                _images_aff -= _images_aff.min()
                _images_aff /= _images_aff.max()
                _images_aff *= 255
                _images_aff = _images_aff.transpose((1,2,0))
                pylab.imsave(name, _images_aff.astype('uint8'))
            # save_im(images_aug[0], 'tmp1.png')
            ind = points!=255
            if ind.sum() != 0:
                loss += 2*F.binary_cross_entropy_with_logits(logits[ind], 
                                        points[ind], 
                                        reduction='mean')
                # if flipped:
                #     points_aff = flips.Hflip()(points_aff)
                # logits_flip = self.model_base(flips.Hflip()(images))
                ind = points_aug != 255
                loss += F.binary_cross_entropy_with_logits(logits_aug[ind], 
                                        points_aug[ind].detach(), 
                                        reduction='mean')

        elif loss_name == 'rot_point_loss':
            points = points[:,None]
            # grid = sst.get_grid(images.shape, normalized=True)
            # images = images[0, None, ...].repeat(8, 1, 1, 1)
            rotations = np.random.choice([0, 90, 180, 270], points.shape[0], replace=True)
            images = flips.Hflip()(images)
            images_rotated = sst.batch_rotation(images, rotations)
            logits_rotated = self.model_base(images_rotated)
            logits_recovered = sst.batch_rotation(logits_rotated, 360 - rotations)
            logits_recovered = flips.Hflip()(logits_recovered)
            
            loss = torch.mean(torch.abs(logits_recovered-logits))
            
            ind = points!=255
            if ind.sum() != 0:
                loss += F.binary_cross_entropy_with_logits(logits[ind], 
                                        points[ind].detach().float().cuda(), 
                                        reduction='mean')

                points_rotated = flips.Hflip()(points)
                points_rotated = sst.batch_rotation(points_rotated, rotations)
                ind = points_rotated!=255
                loss += F.binary_cross_entropy_with_logits(logits_rotated[ind], 
                                        points_rotated[ind].detach().float().cuda(), 
                                        reduction='mean')

        elif loss_name == 'lcfcn_loss':
            loss = 0.
  
            for lg, pt in zip(logits, points):
                loss += lcfcn_loss.compute_loss((pt==1).long(), lg.sigmoid())

                # loss += lcfcn_loss.compute_binary_lcfcn_loss(l[None], 
                #         p[None].long().cuda())

        elif loss_name == 'point_level':
            
            class_labels = torch.zeros(self.n_classes).cuda().long()
            class_labels[np.unique([p['cls'] for p in point_list[0]])] = 1
            n,c,h,w = logits.shape
            class_logits = logits.view(n,c,h*w)
            # REGION LOSS
            loss = F.multilabel_soft_margin_loss(class_logits.max(2)[0], 
                                                    class_labels[None], reduction='mean')

            # POINT LOSS
            points = torch.ones(h,w).cuda()*255
            for p in point_list[0]:
                if p['y'] >= h or p['x'] >= w: 
                    continue
                points[int(p['y']), int(p['x'])] = p['cls']
            probs = F.log_softmax(logits, dim=1)
            loss += F.nll_loss(probs, 
                            points[None].long(), reduction='mean', ignore_index=255)

            return loss

        elif loss_name == 'point_loss':
            points = points[:,None]
            ind = points!=255
            # self.vis_on_batch(batch, savedir_image='tmp.png')

            # POINT LOSS
            # loss = ut.joint_loss(logits, points[:,None].float().cuda(), ignore_index=255)
            # print(points[ind].sum())
            if ind.sum() == 0:
                loss = 0.
            else:
                loss = F.binary_cross_entropy_with_logits(logits[ind], 
                                        points[ind].float().cuda(), 
                                        reduction='mean')
                                        
            # print(points[ind].sum().item(), float(loss))
        elif loss_name == 'att_point_loss':
            points = points[:,None]
            ind = points!=255

            loss = 0.
            if ind.sum() != 0:
                loss = F.binary_cross_entropy_with_logits(logits[ind], 
                                        points[ind].float().cuda(), 
                                        reduction='mean')

                logits_flip = self.model_base(flips.Hflip()(images))
                points_flip = flips.Hflip()(points)
                ind = points_flip!=255
                loss += F.binary_cross_entropy_with_logits(logits_flip[ind], 
                                        points_flip[ind].float().cuda(), 
                                        reduction='mean')

        elif loss_name == 'cons_point_loss':
            points = points[:,None]
            
            logits_flip = self.model_base(flips.Hflip()(images))
            loss = torch.mean(torch.abs(flips.Hflip()(logits_flip)-logits))
            
            ind = points!=255
            if ind.sum() != 0:
                loss += F.binary_cross_entropy_with_logits(logits[ind], 
                                        points[ind].float().cuda(), 
                                        reduction='mean')

                points_flip = flips.Hflip()(points)
                ind = points_flip!=255
                loss += F.binary_cross_entropy_with_logits(logits_flip[ind], 
                                        points_flip[ind].float().cuda(), 
                                        reduction='mean')

        return loss